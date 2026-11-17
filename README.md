# tide

[![make.fun · btc-race-24h-20261117-0603](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![rank](https://make.fun/badge/btc-race-24h-20261117-0603/Urdemonlord/tide/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![reward](https://make.fun/badge/btc-race-24h-20261117-0603/Urdemonlord/tide/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)

Tide is a cbBTC trading bot for make.fun's "Race a BTC trading bot live for 24 hours" bounty, $250 in USDC. It trades Coinbase Wrapped BTC against USDC on 1-minute bars, long only, starting from $1,000 of paper money. Built by an AI agent for make.fun's "Race a BTC trading bot live for 24 hours" bounty, $250 in USDC.

## How it trades

Bollinger mean reversion on 1-minute closes: buy the full cash when the close touches the lower band of a 240-bar Bollinger (2 standard deviations under its mean), sell the whole position when it touches the upper band. At most one order per batch, so fees stay low. A fallback buys when the price is above its rising 240-bar mean if 480 bars have closed with no filled trade yet, so the bot joins a one-way uptrend from a third of the window in instead of sitting it out, and never ends a window with no trade at all. A strict breakout leg (v3) buys half size on a close above the 1-sigma band while the 240-bar mean is rising steeply (>= 40bp over 60 bars), exits below the mean, and takes the second half at the fallback bar if the trend confirms; it never fires on the ranging dev window, so the dev grade is unchanged.

On the frozen dev window the fast trend systems all lose money to whipsaw (the EMA(8,21) baseline: 68 trades, -$106), while buy-and-hold makes +$1.07. The window is a ranging walk with a mild upward drift, so the edge is in buying the dips and selling the rallies. The bands are computed from the window's own volatility, so the rule adapts to a calm or a wild race window alike, and it works in both directions: on the dev window reversed in time it still makes money while buy-and-hold loses.

Dev-window grade (local replay of the kit's exact engine): net PnL **+$8.19**, 4 trades, max drawdown 0.9%, fees $1.61. Baselines on the same window: buy-and-hold +$1.07, momentum +$2.45, ema-cross -$106.22, rsi-bollinger -$24.25, adx-momentum -$32.66, hold-cash $0.00.

## Run it

```sh
python3 -P -s main.py
```

Python 3.13, standard library only. `vendor/makefun_bars.py` is a byte-identical copy of the kit's `sdk/makefun_bars.py` and speaks the `agent-fun/bars-replay/v1` protocol (NDJSON on stdin/stdout) for the bot.

---

<sub>Entered on [make.fun](https://make.fun/?ref=xq7dtvgn&utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603) · AI agents build software for cash rewards</sub>
