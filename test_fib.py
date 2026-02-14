"""Quick test of Fibonacci analysis on live Kraken data"""
from rimuru_auto_trader import KrakenClient, TA, Config
import time

# Load keys
api_key = api_secret = ''
for line in open('_SENSITIVE/kraken_keys.txt'):
    line = line.strip()
    if line.startswith('KRAKEN_API_KEY='): api_key = line.split('=',1)[1]
    elif line.startswith('KRAKEN_API_SECRET='): api_secret = line.split('=',1)[1]

client = KrakenClient(api_key, api_secret)

for name, pair, tf in [('SOL', 'SOLUSD', 15), ('DOGE', 'XDGUSD', 15), ('BTC', 'XXBTZUSD', 60), ('ETH', 'XETHZUSD', 60)]:
    print(f"\n{'='*50}")
    print(f"  FIBONACCI: {name} ({pair}) - {tf}m candles")
    print(f"{'='*50}")
    
    candles = client.ohlc(pair, tf)
    current = float(candles[-1][4]) if candles else 0
    print(f"  Current price: ${current:.4f}")
    
    fib = TA.fibonacci(candles, 50)
    if fib:
        print(f"  Trend: {fib['trend'].upper()}")
        print(f"  Swing: ${fib['swing_low']:.4f} - ${fib['swing_high']:.4f} ({fib['range_pct']:.1f}% range)")
        print(f"  Zone: {fib['zone']} (Fib position: {fib['fib_position']:.3f})")
        print(f"  Support: ${fib['support']:.4f}")
        print(f"  Resistance: ${fib['resistance']:.4f}")
        print(f"  Retracement levels:")
        for k, v in sorted(fib['levels'].items()):
            marker = ' <-- PRICE HERE' if abs(v - current) / max(v, 0.0001) < 0.005 else ''
            print(f"    Fib {k}: ${v:.4f}{marker}")
        print(f"  Extension targets:")
        for k, v in sorted(fib['extensions'].items()):
            print(f"    Fib {k}: ${v:.4f}")
        
        # RSI for context
        closes = [float(c[4]) for c in candles]
        rsi = TA.rsi(closes)
        print(f"  RSI: {rsi:.1f}" if rsi else "  RSI: N/A")
    else:
        print("  Not enough data for Fib")
    
    time.sleep(1)

print(f"\n{'='*50}")
print("  Fibonacci analysis complete")
print(f"{'='*50}")
