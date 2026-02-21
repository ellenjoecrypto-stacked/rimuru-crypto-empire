"""
Rimuru Crypto Empire — Executor Service
Manages order placement, risk checks, paper/live toggle,
position tracking, and order idempotency.
"""

from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import sys
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.config import ServiceConfig
from shared.kraken_client import KrakenClient
from shared.models import (
    OrderRequest,
    OrderResult,
    PortfolioState,
    Position,
    PositionStatus,
    ServiceHealth,
)
from shared.security import secure_app

logger = logging.getLogger("rimuru.executor")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Rimuru Executor", version="2.0.0")
secure_app(app)
START_TIME = time.time()

# --------------- State ---------------
kraken: KrakenClient = None
positions: dict[str, Position] = {}
order_ledger: list[dict] = []
daily_pnl: float = 0.0
daily_trades: int = 0
daily_loss_limit_hit: bool = False
PAPER_MODE = ServiceConfig.PAPER_MODE
DATA_DIR = Path(os.getenv("DATA_DIR", "data/executor"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_kraken() -> KrakenClient:
    global kraken
    if kraken is None:
        key, secret = ServiceConfig.load_kraken_keys()
        kraken = KrakenClient(key, secret)
    return kraken


def _save_state():
    state = {
        "positions": {k: v.model_dump() for k, v in positions.items()},
        "daily_pnl": daily_pnl,
        "daily_trades": daily_trades,
        "order_ledger": order_ledger[-100:],  # keep last 100
    }
    (DATA_DIR / "executor_state.json").write_text(json.dumps(state, indent=2))


def _load_state():
    global daily_pnl, daily_trades, order_ledger
    path = DATA_DIR / "executor_state.json"
    if path.exists():
        try:
            state = json.loads(path.read_text())
            for k, v in state.get("positions", {}).items():
                positions[k] = Position(**v)
            daily_pnl = state.get("daily_pnl", 0)
            daily_trades = state.get("daily_trades", 0)
            order_ledger = state.get("order_ledger", [])
            logger.info("Loaded state: %s positions, %s trades today", len(positions), daily_trades)
        except Exception:
            logger.exception("Failed to load state")


# Load on startup
_load_state()


# --------------- Risk Checks ---------------


def _risk_check(req: OrderRequest) -> str:
    """Returns error message if risk check fails, empty string if OK"""
    if daily_loss_limit_hit:
        return "Daily loss limit reached — trading paused"

    if abs(daily_pnl) > ServiceConfig.DAILY_LOSS_LIMIT:
        return f"Daily loss ${daily_pnl:.2f} exceeds limit ${ServiceConfig.DAILY_LOSS_LIMIT}"

    if req.side.value == "buy" and len(positions) >= ServiceConfig.MAX_OPEN_POSITIONS:
        return f"Max open positions reached ({ServiceConfig.MAX_OPEN_POSITIONS})"

    vol_usd = req.volume * (req.price or 0)
    min_vol = ServiceConfig.MIN_ORDER.get(req.pair, 0)

    if vol_usd > ServiceConfig.MAX_TRADE_USD:
        error = f"Order ${vol_usd:.2f} exceeds max trade ${ServiceConfig.MAX_TRADE_USD}"
    elif vol_usd < ServiceConfig.MIN_TRADE_USD:
        error = f"Order ${vol_usd:.2f} below min trade ${ServiceConfig.MIN_TRADE_USD}"
    elif req.volume < min_vol:
        error = f"Volume {req.volume} below Kraken minimum {min_vol} for {req.pair}"
    else:
        error = ""

    return error


# --------------- Endpoints ---------------


@app.get("/health")
def health():
    return ServiceHealth(
        service="executor",
        status="healthy",
        uptime_seconds=round(time.time() - START_TIME, 1),
        details={
            "paper_mode": PAPER_MODE,
            "open_positions": len(positions),
            "daily_trades": daily_trades,
            "daily_pnl": round(daily_pnl, 2),
        },
    )


@app.post("/execute")
def execute_order(req: OrderRequest):
    """Execute an order with risk checks"""
    global daily_trades, daily_pnl

    now = datetime.now(UTC).isoformat()

    # Risk check
    risk_error = _risk_check(req)
    if risk_error:
        return OrderResult(
            success=False,
            pair=req.pair,
            side=req.side.value,
            error=risk_error,
            timestamp=now,
        )

    # Paper mode or validate only
    if PAPER_MODE or req.validate_only:
        price = req.price or 0
        result = OrderResult(
            success=True,
            order_id=f"PAPER-{int(time.time() * 1000)}",
            pair=req.pair,
            side=req.side.value,
            volume=req.volume,
            price=price,
            cost_usd=req.volume * price,
            fee=req.volume * price * 0.0026,  # Kraken taker fee
            timestamp=now,
        )
        logger.info(
            "[PAPER] %s %s %s @ $%s", req.side.value.upper(), req.volume, req.pair, f"{price:.6f}"
        )
    else:
        # LIVE order
        kc = get_kraken()
        try:
            api_result = kc.place_order(
                pair=req.pair,
                side=req.side.value,
                order_type=req.order_type.value,
                volume=req.volume,
                price=req.price,
            )
            txid = (
                api_result.get("txid", [""])[0] if isinstance(api_result.get("txid"), list) else ""
            )
            result = OrderResult(
                success=True,
                order_id=txid,
                pair=req.pair,
                side=req.side.value,
                volume=req.volume,
                price=req.price or 0,
                cost_usd=req.volume * (req.price or 0),
                timestamp=now,
            )
            logger.info("[LIVE] %s %s %s -> %s", req.side.value.upper(), req.volume, req.pair, txid)
        except Exception as e:
            logger.exception("Order failed")
            return OrderResult(
                success=False,
                pair=req.pair,
                side=req.side.value,
                error=str(e),
                timestamp=now,
            )

    # Track position
    if result.success and req.side.value == "buy":
        positions[req.pair] = Position(
            pair=req.pair,
            side="long",
            entry_price=result.price,
            volume=result.volume,
            entry_time=now,
            strategy=req.strategy,
            order_id=result.order_id,
            stop_loss=req.stop_loss or 0,
            take_profit=req.take_profit or 0,
        )
    elif result.success and req.side.value == "sell" and req.pair in positions:
        pos = positions[req.pair]
        pos.status = PositionStatus.CLOSED
        pnl = (result.price - pos.entry_price) * result.volume
        daily_pnl += pnl
        del positions[req.pair]

    daily_trades += 1

    # Audit log
    order_ledger.append(
        {
            "time": now,
            "pair": req.pair,
            "side": req.side.value,
            "volume": req.volume,
            "price": result.price,
            "success": result.success,
            "order_id": result.order_id,
            "strategy": req.strategy,
            "paper": PAPER_MODE,
        }
    )
    _save_state()

    return result


@app.get("/positions")
def get_positions():
    return {"positions": {k: v.model_dump() for k, v in positions.items()}}


@app.get("/portfolio")
def get_portfolio():
    kc = get_kraken()
    try:
        bal = kc.balance()
        tb = kc.trade_balance()
        return PortfolioState(
            total_usd=float(tb.get("eb", 0)),
            available_usd=float(bal.get("ZUSD", 0)),
            open_positions=list(positions.values()),
            daily_pnl=round(daily_pnl, 2),
            daily_trades=daily_trades,
            balances={k: float(v) for k, v in bal.items() if float(v) > 0},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/ledger")
def get_ledger(limit: int = 50):
    return {"orders": order_ledger[-limit:]}


@app.post("/paper-mode/{enabled}")
def set_paper_mode(enabled: bool):
    global PAPER_MODE
    PAPER_MODE = enabled
    logger.warning("Paper mode %s", "ENABLED" if enabled else "DISABLED")
    return {"paper_mode": PAPER_MODE}


@app.post("/emergency-stop")
def emergency_stop():
    """Cancel all open orders and pause trading"""
    global daily_loss_limit_hit
    daily_loss_limit_hit = True
    logger.critical("EMERGENCY STOP activated")

    if not PAPER_MODE:
        kc = get_kraken()
        try:
            open_orders = kc.open_orders()
            for txid in open_orders:
                kc.cancel_order(txid)
                logger.info("Cancelled order %s", txid)
        except Exception:
            logger.exception("Error cancelling orders")

    return {"status": "EMERGENCY STOP ACTIVE", "positions_frozen": len(positions)}


@app.get("/metrics")
def prometheus_metrics():
    lines = [
        f"rimuru_executor_uptime {time.time() - START_TIME:.1f}",
        f"rimuru_executor_daily_trades {daily_trades}",
        f"rimuru_executor_daily_pnl {daily_pnl:.4f}",
        f"rimuru_executor_open_positions {len(positions)}",
        f"rimuru_executor_paper_mode {int(PAPER_MODE)}",
        f"rimuru_executor_emergency_stop {int(daily_loss_limit_hit)}",
    ]
    return JSONResponse(content="\n".join(lines), media_type="text/plain")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8020"))
    logger.info("Rimuru Executor starting on port %s [%s]", port, "PAPER" if PAPER_MODE else "LIVE")
    uvicorn.run(app, host="0.0.0.0", port=port)
