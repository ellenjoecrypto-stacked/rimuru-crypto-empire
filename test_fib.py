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
    print(f"\n{'='*50} - test_fib.py:15")
    print(f"FIBONACCI: {name} ({pair})  {tf}m candles - test_fib.py:16")
    print(f"{'='*50} - test_fib.py:17")
    
    candles = client.ohlc(pair, tf)
    current = float(candles[-1][4]) if candles else 0
    print(f"Current price: ${current:.4f} - test_fib.py:21")
    
    fib = TA.fibonacci(candles, 50)
    if fib:
        print(f"Trend: {fib['trend'].upper()} - test_fib.py:25")
        print(f"Swing: ${fib['swing_low']:.4f}  ${fib['swing_high']:.4f} ({fib['range_pct']:.1f}% range) - test_fib.py:26")
        print(f"Zone: {fib['zone']} (Fib position: {fib['fib_position']:.3f}) - test_fib.py:27")
        print(f"Support: ${fib['support']:.4f} - test_fib.py:28")
        print(f"Resistance: ${fib['resistance']:.4f} - test_fib.py:29")
        print(f"Retracement levels: - test_fib.py:30")
        for k, v in sorted(fib['levels'].items()):
            marker = ' <-- PRICE HERE' if abs(v - current) / max(v, 0.0001) < 0.005 else ''
            print(f"Fib {k}: ${v:.4f}{marker} - test_fib.py:33")
        print(f"Extension targets: - test_fib.py:34")
        for k, v in sorted(fib['extensions'].items()):
            print(f"Fib {k}: ${v:.4f} - test_fib.py:36")
        
        # RSI for context
        closes = [float(c[4]) for c in candles]
        rsi = TA.rsi(closes)
        print(f"RSI: {rsi:.1f} - test_fib.py:41" if rsi else "  RSI: N/A")
    else:
        print("Not enough data for Fib - test_fib.py:43")
    
    time.sleep(1)

print(f"\n{'='*50} - test_fib.py:47")
print("Fibonacci analysis complete - test_fib.py:48")
print(f"{'='*50} - test_fib.py:49")
