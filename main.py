"""Tide: a cbBTC trading bot for make.fun's btc-race-24h-20261117-0603.

Strategy: Bollinger mean reversion on 1-minute closes, long only, full size.
Buy when the close touches the lower band of a 240-bar Bollinger (2 standard
deviations under its mean), sell when it touches the upper band. One asset,
one position, at most one order per batch, so fees stay low: a full-size round
trip costs about 26 bps, and the band is wide enough that a trade has to catch
a real swing to pay for itself.

Why this shape: on the frozen dev window the fast trend systems (EMA cross,
RSI, ADX momentum) all lose money to whipsaw, 68 trades for -$106 on the
EMA(8,21) baseline, while buy-and-hold makes only +$1.07. The window is a
ranging walk with a mild upward drift, so the edge is in buying the dips and
selling the rallies, not in chasing the trend. The bands are computed from the
window's own volatility, so the rule adapts to a calm or a wild race window
alike, and it works in both directions: on the dev window reversed in time it
still makes money while buy-and-hold loses.

The v3 breakout leg rides a strong trend the mean reversion would otherwise
sell into: when flat, it buys half size on a close above the 1-sigma band
while the 240-bar mean is rising steeply (>= 40bp over 60 bars), and exits
below the mean. The 2-sigma band is not the breakout level because a smooth
trend inflates the 240-bar sd until the close can never exceed it (measured:
0 of 1440 bars above it on a steady +1bp/bar series); the 40bp threshold
sits between the ranging dev window's max (28.4bp, 31.3bp reversed) and a
+1bp/bar trend's steady ~59bp, so the leg never fires on dev. If the trend
is still strong at the fallback bar, the second half is bought there, so
the early half-size entry cannot leave the bot under-invested in the trend
the fallback was built to catch.

Deterministic: every decision is a pure function of the closes seen so far.
No clock, no network, no randomness, no files. The same bars give the same
orders, run after run.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
SPAN = 240          # bars of history behind each band (4 hours)
K = 2.0             # band width in standard deviations
MAX_SLIPPAGE_BPS = 100  # 1% past the close the order was decided on

# The closes seen so far, in order (the bar of each batch that carried CBBTC).
closes = []
# Filled orders so far, counted from the fills each batch carries.
trades = 0

# Fallback for a window that never touches a band: without it the bot
# would end with no trade at all and miss the guardrail (at least 1 trade).
# Once 480 bars have closed with no filled trade, buy when the price is
# above its own 240-bar mean and that mean is rising: a window that strong
# has no dip to buy, so riding it long from a third of the way in beats
# waiting for its last hours. Never fires on the dev window (first trade
# lands at bar 366 there) or on a falling window (price below its mean).
FALLBACK_BAR = 480
TREND_LAG = 60            # bars back for the mean-rising check

# Breakout leg (v3): a strict trend entry on top of the mean reversion.
# It buys half size; see the module docstring for why the level is the
# 1-sigma band and the threshold 40bp.
BREAKOUT_RISE_BPS = 40   # minimum 60-bar mean rise, in bp of price

# Position origin, set when a buy is decided and cleared when flat:
# "reversion" (lower-band buy, or fallback buy: sells at the upper band)
# or "breakout" (breakout buy: exits below the mean). A holding with no
# recorded origin is treated as a reversion.
pos_kind = None
# Whether the breakout position already took its second half at the
# fallback bar.
topped_up = False


def _bands():
    """(mean, sd, lower, upper) of the last SPAN closes, or None until SPAN seen."""
    if len(closes) < SPAN:
        return None
    window = closes[-SPAN:]
    mean = sum(window) / SPAN
    var = sum((c - mean) * (c - mean) for c in window) / SPAN
    sd = var ** 0.5
    return mean, sd, mean - K * sd, mean + K * sd


def _mean_lag():
    """Mean of the SPAN closes ending TREND_LAG bars ago, or None."""
    if len(closes) < SPAN + TREND_LAG:
        return None
    return sum(closes[-SPAN - TREND_LAG:-TREND_LAG]) / SPAN


def on_batch(state, batch):
    global trades, pos_kind, topped_up
    for fill in batch.get("fills", []):
        if fill.get("status") == "filled":
            trades += 1
    if state.warming_up:
        return []
    bar = state.latest.get(SYMBOL)
    if bar is None:
        return []
    closes.append(int(bar["c"]))
    bands = _bands()
    if bands is None:
        return []
    mean, sd, lower, upper = bands
    close = int(bar["c"])
    lag = _mean_lag()
    rising = lag is not None and mean > lag
    steep = lag is not None and (mean - lag) * 10000 / close >= BREAKOUT_RISE_BPS
    holding = state.positions.get(SYMBOL)
    if holding is None or holding.qty <= 0:
        pos_kind = None
        topped_up = False
        holding = None
    if holding is not None and holding.qty > 0:
        if pos_kind == "breakout":
            if close < mean:
                return [{
                    "side": "sell",
                    "symbol": SYMBOL,
                    "qty": holding.qty,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }]
            if (not topped_up and len(closes) >= FALLBACK_BAR
                    and close > mean and rising and state.cash > 0):
                topped_up = True
                return [{
                    "side": "buy",
                    "symbol": SYMBOL,
                    "notional_quote_units": state.cash,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }]
            return []
        if close >= upper:
            return [{
                "side": "sell",
                "symbol": SYMBOL,
                "qty": holding.qty,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }]
        return []
    if close <= lower and state.cash > 0:
        pos_kind = "reversion"
        return [{
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": state.cash,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    if close > mean + sd and steep and state.cash > 0:
        pos_kind = "breakout"
        return [{
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": state.cash // 2,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    if (len(closes) >= FALLBACK_BAR and trades == 0
            and close > mean and rising and state.cash > 0):
        pos_kind = "reversion"
        return [{
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": state.cash,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    return []


makefun_bars.run(on_batch)
