# Cashflip Game Engine — Deep Analytics Audit
**Date**: 19 Feb 2026  
**Server**: demo.console.cashflip.amoano.com  
**Data**: 26 sessions, 121 flips, 2 players

---

## EXECUTIVE SUMMARY

**The house is losing money. The game engine has a critical mathematical flaw.**

| Metric | Value |
|---|---|
| Total Staked | GHS 94.00 |
| Total Paid Out | GHS 151.00 |
| **House P&L** | **GHS −57.00** |
| **Actual House Edge** | **−60.64%** (house LOSES 60¢ per GHS 1 staked) |
| Configured House Edge | 60.00% (house should KEEP 60¢ per GHS 1) |

The `house_edge_percent` setting is **cosmetic only** — it is never referenced in the game engine code (`engine.py`). The actual house edge is determined entirely by the interaction of the zero probability curve and the denomination values/weights, which are currently catastrophically mismatched.

---

## 1. SESSION DATA

### All 26 Sessions

| # | Status | Stake | Cashout | Flips | House P&L | Player |
|---|--------|-------|---------|-------|-----------|--------|
| 1 | lost | 1.00 | 0.00 | 3 | +1.00 | BoldBoss32 |
| 2 | lost | 1.00 | 0.00 | 3 | +1.00 | BoldBoss32 |
| 3–7 | lost | 1.00 | 0.00 | 4–5 | +1.00 ea | BoldTitan33 |
| **8** | **cashed_out** | **1.00** | **22.00** | **2** | **−21.00** | BoldTitan33 |
| 9–17 | lost | 1–5 | 0.00 | 4–8 | +1–5 ea | BoldTitan33 |
| **18** | **cashed_out** | **1.00** | **26.00** | **3** | **−25.00** | BoldTitan33 |
| **20** | **cashed_out** | **1.00** | **52.00** | **3** | **−51.00** | BoldTitan33 |
| **21** | **cashed_out** | **1.00** | **16.00** | **3** | **−15.00** | BoldTitan33 |
| 25 | cashed_out | 50.00 | 9.00 | 4 | +41.00 | BoldTitan33 |

**Key observation**: Session #20 — player staked GHS 1, got flips of GHS 1 + GHS 1 + GHS 50, cashed out GHS 52. That's a **5,100% ROI** on a single game.

### Per-Player P&L

| Player | Games | W/L | Staked | Won | House P&L |
|--------|-------|-----|--------|-----|-----------|
| BoldBoss32 | 2 | 0W/2L | 2.00 | 0.00 | +2.00 |
| BoldTitan33 | 24 | 8W/16L | 92.00 | 151.00 | **−59.00** |

---

## 2. THE THREE CRITICAL FLAWS

### Flaw 1: `house_edge_percent` Is a Dead Setting

```python
# game/models.py — GameConfig
house_edge_percent = models.DecimalField(default=60.00)
```

**This field is NEVER read by `game/engine.py`**. It exists in the admin panel purely as a label. The actual house edge is an emergent property of:
- Zero probability curve parameters (`zero_base_rate`, `zero_growth_rate`, `min_flips_before_zero`)
- Denomination values and weights

These two systems are **completely disconnected** — there is no code that links them.

### Flaw 2: Denomination Values Are Absolute, Not Stake-Relative

Current denominations (for GHS currency):

| Value | Weight | Selection % | Contribution to EV |
|-------|--------|-------------|-------------------|
| GHS 1 | 30 | 29.7% | GHS 0.30 |
| GHS 2 | 25 | 24.8% | GHS 0.50 |
| GHS 5 | 20 | 19.8% | GHS 0.99 |
| GHS 10 | 12 | 11.9% | GHS 1.19 |
| GHS 20 | 8 | 7.9% | GHS 1.58 |
| GHS 50 | 4 | 4.0% | GHS 1.98 |
| GHS 100 | 1 | 1.0% | GHS 0.99 |
| GHS 200 | 1 | 1.0% | GHS 1.98 |
| **Total** | **101** | **100%** | **GHS 9.50** |

**Expected value per winning flip: GHS 9.50**

A player staking GHS 1 gets **9.5x their stake** on every winning flip. This is independent of what they staked — a GHS 1 stake and a GHS 50 stake both draw from the same GHS 1–200 denomination pool.

### Flaw 3: Guaranteed Safe Flips = Guaranteed Profit

With `min_flips_before_zero = 2`, flips 1 and 2 have **zero probability of loss**. Since the minimum denomination is GHS 1 (equal to the minimum stake), a player can:

1. Stake GHS 1
2. Flip once (guaranteed safe) → wins at least GHS 1
3. Cash out immediately

**Result: risk-free breakeven or profit on every single game.** On average, the player gets GHS 9.50 from a single guaranteed-safe flip on a GHS 1 stake.

---

## 3. MATHEMATICAL ANALYSIS

### Zero Probability Curve

Formula: `P(zero) = 0.05 + 0.95 × (1 − e^(−0.08 × (flip − 2)))`

| Flip | P(zero) | P(survive) | Cum. Survival |
|------|---------|------------|---------------|
| 1 | 0.0% | 100.0% | 100.00% |
| 2 | 0.0% | 100.0% | 100.00% |
| 3 | 12.3% | 87.7% | 87.70% |
| 4 | 19.1% | 80.9% | 70.99% |
| 5 | 25.3% | 74.7% | 53.05% |
| 6 | 31.0% | 69.0% | 36.60% |
| 7 | 36.3% | 63.7% | 23.31% |
| 8 | 41.2% | 58.8% | 13.70% |
| 10 | 49.9% | 50.1% | 3.72% |
| 15 | 66.4% | 33.6% | 0.04% |

The curve is **extremely gentle** for a game awarding GHS 9.50 per flip.

### Expected Payout Per Strategy (for GHS 1 stake)

| Strategy: Cash after flip | P(success) | Expected Payout | ROI |
|--------------------------|------------|-----------------|-----|
| 1 (guaranteed safe) | 100.0% | GHS 9.50 | **+850%** |
| 2 (guaranteed safe) | 100.0% | GHS 19.01 | **+1,801%** |
| 3 | 87.7% | GHS 25.01 | **+2,401%** |
| **4 (optimal)** | **71.0%** | **GHS 26.99** | **+2,599%** |
| 5 | 53.1% | GHS 25.21 | +2,421% |
| 8 | 13.7% | GHS 10.42 | +942% |
| 11 | 1.7% | GHS 1.80 | +80% |
| 12+ | <1% | <GHS 1.00 | negative |

**Every strategy from "cash after 1 flip" through "cash after 11 flips" is profitable for the player.** The house only wins if the player plays past flip 12.

### Play-Until-Loss Expected Payout

For a player who never cashes out (plays until zero), the expected total payout is:

**GHS 47.47 per GHS 1 staked** (the house edge is −4,647%)

Expected surviving flips per session: **4.99**

### What The Denomination EV Should Be

For a 60% house edge with the current zero curve (k=0.08):
- Required EV per winning flip: **GHS 0.08**
- Current EV per winning flip: **GHS 9.50**
- **The denominations are 119× too high**

---

## 4. ACTUAL vs EXPECTED OUTCOMES

| Flip # | Total Flips | Actual Zeros | Actual % | Expected % | Delta |
|--------|------------|-------------|---------|-----------|-------|
| 1 | 26 | 0 | 0.0% | 0.0% | ±0% |
| 2 | 26 | 0 | 0.0% | 0.0% | ±0% |
| 3 | 25 | 2 | 8.0% | 12.3% | −4.3% |
| 4 | 19 | 3 | 15.8% | 19.0% | −3.3% |
| 5 | 14 | 6 | 42.9% | 25.3% | +17.6% |
| 6 | 7 | 4 | 57.1% | 31.0% | +26.1% |
| 7 | 3 | 2 | 66.7% | 36.3% | +30.3% |

**Note**: Small sample size (26 sessions) so variance is expected. The curve implementation itself is mathematically correct — the problem is the parameters, not the code.

---

## 5. IDENTIFIED LOOPHOLES & EXPLOITS

### 🔴 Critical: Risk-Free Profit (Guaranteed Safe Flips)

**Exploit**: Stake GHS 1 → flip once → cash out GHS 1–200 (always profitable, zero risk).

With 2 guaranteed safe flips and a minimum denomination ≥ minimum stake, there is **no scenario where the player loses money** if they cash out within 2 flips. The expected return for this exploit is **+850% to +1,801%**.

### 🔴 Critical: No Minimum Flip Requirement for Cashout

The cashout view (`views.py:248`) only checks `cashout_balance > 0`. There is no minimum flip count requirement. Players can cash out after a single flip.

### 🔴 Critical: Denomination Pool Independent of Stake

A GHS 1 stake draws from the same GHS 1–200 denomination pool as a GHS 50 stake. This creates extreme variance and a negative house edge for low-stake players.

### 🟡 Medium: No Cashout Cap Enforcement Per Session

While `max_cashout = 10,000` exists in config, it's never checked during cashout. A player who gets lucky with high denominations could cash out an unlimited amount.

### 🟡 Medium: Auto-Flip Timer Creates False Urgency Only

The 8-second auto-flip timer exists in the JS client but the server doesn't enforce it. A player could disable JS, hold their session indefinitely, and cash out whenever they want.

### 🟢 Low: Client-Side Cashout Button Logic

The cashout button is enabled as soon as `cashout_balance > 0` (after any winning flip). There's no client-side delay or minimum-flip gate.

---

## 6. RECOMMENDATIONS

### Immediate Fix (Critical — Do Before Production)

**Option A: Stake-Based Multiplier System** (Recommended)

Replace absolute denomination values with **multipliers of the stake**:

| Multiplier | Weight | For GHS 1 stake | For GHS 50 stake |
|-----------|--------|-----------------|-----------------|
| 0.1x | 30 | GHS 0.10 | GHS 5.00 |
| 0.2x | 25 | GHS 0.20 | GHS 10.00 |
| 0.3x | 20 | GHS 0.30 | GHS 15.00 |
| 0.5x | 12 | GHS 0.50 | GHS 25.00 |
| 0.8x | 8 | GHS 0.80 | GHS 40.00 |
| 1.0x | 4 | GHS 1.00 | GHS 50.00 |
| 2.0x | 1 | GHS 2.00 | GHS 100.00 |

This gives EV per flip ≈ 0.30x stake. With the current curve, the house edge would be approximately +40%.

**Option B: Dramatically Reduce Denominations**

Keep absolute values but reduce them to:
GHS 0.05, 0.10, 0.20, 0.50, 1.00, 2.00, 5.00

**Option C: Aggressive Zero Curve**

Increase `k` to ~3.0+ (from 0.08) and remove guaranteed safe flips. But this makes the game feel punishing.

### Structural Fixes

1. **Wire `house_edge_percent` into the engine** — either use it to dynamically calculate zero probability, or use it to scale denomination payouts.

2. **Add minimum flip requirement for cashout** — e.g., player must flip at least 3 times before cashing out. This removes the guaranteed-profit exploit.

3. **Enforce `max_cashout` server-side** — cap `session.cashout_balance` at `config.max_cashout` in `execute_flip`.

4. **Server-side auto-flip enforcement** — if auto-flip is enabled, the server should auto-execute a flip if the player idles, not rely on JS.

5. **Denomination-stake proportionality** — the engine should select denominations proportional to the stake, not from a fixed pool.

### Recommended Parameter Set (For 60% House Edge)

Using multiplier system with current curve (k=0.08, base=0.05, min_flips=2):

```
EV per win flip needed: ~0.08x stake
Multipliers: 0.02x(40), 0.05x(30), 0.08x(15), 0.10x(10), 0.20x(4), 0.50x(1)
Weighted EV = 0.06x per flip
Expected surviving flips = 4.99
Total EV = 4.99 × 0.06 = 0.30x stake
House edge = 70% ✓
```

Alternatively, keep current multiplier spread but increase k to 0.6:

```
With k=0.6: expected surviving flips ≈ 1.8
With current EV 9.50: total EV = 1.8 × 9.50 = 17.1 (still way too high for GHS 1 stake)
```

**Conclusion**: Adjusting k alone cannot fix this. The denomination values MUST be proportional to the stake.

---

## 7. HOW FLIP COUNTING SHOULD WORK

Current: `flip_count` increments by 1 every flip, starting from 1. This is correct.

Recommended flow:
1. Flip 1: always safe, awards small multiplier of stake
2. Flip 2: always safe, awards small multiplier of stake  
3. Flip 3+: zero probability escalates per curve
4. **Minimum 1 flip before cashout** (removes zero-flip cashout edge case)
5. Running cashout balance accumulates multiplier × stake
6. Player decides: flip again (risk losing everything) or cash out (keep accumulated)

The escalating-risk mechanic is sound — the issue is purely numerical (denomination values are 119× too large relative to the zero curve's pace).

---

*Report generated from live database analysis on demo server.*
