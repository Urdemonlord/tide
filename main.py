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

# Late fallback: if the window never touches a band, the bot would end with
# no trade at all and miss the guardrail (at least 1 trade). Once 1,200 bars
# have closed with no filled trade, buy when the price is above its own
# 240-bar mean: a window that strong has no dip to buy, so riding its last
# hours long is the better seat. Never fires on the dev window (first trade
# lands at bar 365 there).
FALLBACK_BAR = 1200


def _bands():
    """(mean, lower, upper) of the last SPAN closes, or None until SPAN seen."""
    if len(closes) < SPAN:
        return None
    window = closes[-SPAN:]
    mean = sum(window) / SPAN
    var = sum((c - mean) * (c - mean) for c in window) / SPAN
    sd = var ** 0.5
    return mean, mean - K * sd, mean + K * sd


def on_batch(state, batch):
    global trades
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
    mean, lower, upper = bands
    close = int(bar["c"])
    holding = state.positions.get(SYMBOL)
    if holding is not None and holding.qty > 0:
        if close >= upper:
            return [{
                "side": "sell",
                "symbol": SYMBOL,
                "qty": holding.qty,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }]
        return []
    if close <= lower and state.cash > 0:
        return [{
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": state.cash,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    if (len(closes) >= FALLBACK_BAR and trades == 0
            and close > mean and state.cash > 0):
        return [{
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": state.cash,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]
    return []


makefun_bars.run(on_batch)
