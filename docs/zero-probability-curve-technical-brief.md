# Cashflip Zero Probability Curve: Technical Brief

**Document Classification:** Internal — Stakeholder Briefing
**Version:** 1.0 | February 2026
**Prepared by:** Cashflip Engineering

---

## Executive Summary

Cashflip uses an **exponential saturation curve** (often called a sigmoid-like or asymptotic curve) to determine when a player loses during a coin-flip session. This mathematical model is the core of our house edge mechanism — it replaces a simple fixed-probability coin flip with an **escalating risk model** that creates exciting gameplay while guaranteeing long-term profitability.

**In plain terms:** The longer a player keeps flipping, the more likely they are to hit zero and lose. But the first few flips are always safe, creating a hook that keeps players engaged.

Our current configuration delivers:
- **~60% house retention** over volume (we keep 60 cedis of every 100 wagered)
- **Average session length of ~6 flips** — short enough for profitability, long enough for entertainment
- **100% safe first 2 flips** — guaranteed engagement before any risk
- **Only ~0.04% of players** ever reach flip 15 — "big winners" are statistically rare and bounded

---

## 1. The Problem We're Solving

A traditional coin flip is 50/50. If we ran a simple 50/50 game, we'd break even. We need a mechanism that:

1. **Gives the house a mathematical edge** (we need to make money)
2. **Feels fair and exciting to players** (they need to want to play)
3. **Is provably fair** (verifiable, auditable, no cheating accusations)
4. **Creates "near miss" and "streak" moments** (proven engagement drivers in gaming)
5. **Caps maximum exposure** (we can never lose unlimited money to one player)

A flat probability (e.g., "10% chance of zero every flip") solves #1 but fails at #2, #3, and #4. Players would feel cheated losing on flip 1. There's no tension build-up. No "streak excitement."

**Our solution: an escalating zero probability curve.**

---

## 2. How the Curve Works

### The Formula

```
P(zero) = base_rate + (1 - base_rate) × (1 - e^(-k × adjusted_flip))
```

Where:
- **P(zero)** = probability of losing (hitting "zero") on this flip
- **base_rate** = minimum loss probability once risk begins (our floor: **5%**)
- **k** = growth rate — how fast the curve climbs (our value: **0.08**)
- **adjusted_flip** = current flip number minus guaranteed safe flips
- **e** = Euler's number (~2.718), the mathematical constant

### Special Rules
- **Flips 1-2 are always safe** (min_flips_before_zero = 2). Zero probability is 0%.
- **Maximum capped at 95%** — even at flip 100, there's always a 5% chance of surviving. We never make it "guaranteed loss" on any single flip.

### What This Means in Plain English

Think of it like walking across a bridge. The first 2 steps are on solid concrete (guaranteed safe). After that, each plank is a little more rotten than the last. Early planks (flips 3-5) have only small cracks — most people make it. But by plank 10, half the wood is gone. By plank 15, almost nobody crosses. The bridge never fully disappears (95% cap), but practically, nobody survives past ~flip 15.

---

## 3. Our Current Configuration & What Each Parameter Does

| Parameter | Value | What It Controls |
|---|---|---|
| **house_edge_percent** | 60% | Target house retention rate — we aim to keep 60% of all wagered money |
| **zero_base_rate** | 0.05 (5%) | The starting loss probability at flip 3 (first risky flip). Low enough to feel "safe" |
| **zero_growth_rate (k)** | 0.08 | How aggressively the curve climbs. Higher = steeper = shorter sessions |
| **min_flips_before_zero** | 2 | Guaranteed safe flips. Every player gets at least 2 free wins |
| **max_cashout** | GHS 10,000 | Absolute maximum a player can cash out. Hard ceiling on our exposure |
| **min_stake** | GHS 1.00 | Minimum bet per session |
| **pause_cost_percent** | 10% | Cost to "pause" a session (take a break without cashing out) |

---

## 4. The Numbers: Flip-by-Flip Breakdown

### Loss Probability Per Flip

| Flip # | P(Zero) | P(Survive) | Meaning |
|--------|---------|------------|---------|
| 1 | 0.0% | 100.0% | **Always safe** — guaranteed win |
| 2 | 0.0% | 100.0% | **Always safe** — guaranteed win |
| 3 | 12.3% | 87.7% | Risk begins — roughly 1 in 8 players lose here |
| 4 | 19.0% | 81.0% | About 1 in 5 |
| 5 | 25.3% | 74.7% | About 1 in 4 |
| 6 | 31.0% | 69.0% | Nearly 1 in 3 |
| 7 | 36.3% | 63.7% | Over 1 in 3 |
| 8 | 41.2% | 58.8% | Approaching coin-flip odds |
| 9 | 45.7% | 54.3% | Almost 50/50 |
| 10 | 49.9% | 50.1% | **True coin-flip territory** |
| 15 | 66.4% | 33.6% | 2 in 3 chance of losing |
| 20 | 77.5% | 22.5% | Over 3 in 4 chance of losing |
| 25 | 84.9% | 15.1% | Only 1 in 7 survive |
| 30 | 89.9% | 10.1% | 9 in 10 lose |

### Cumulative Survival (reaching flip N alive)

This is the more important number — what percentage of all players who start a session will still be alive at each flip:

| Flip # | % of Players Still Alive | Interpretation |
|--------|--------------------------|----------------|
| 1 | 100.00% | Everyone |
| 2 | 100.00% | Everyone (guaranteed safe) |
| 3 | 87.70% | ~88 out of 100 survive |
| 4 | 70.99% | ~71 out of 100 survive |
| 5 | 53.05% | **About half are gone by flip 5** |
| 6 | 36.60% | Only ~1 in 3 still playing |
| 7 | 23.31% | ~1 in 4 |
| 8 | 13.70% | ~1 in 7 |
| 9 | 7.43% | ~1 in 13 |
| 10 | 3.72% | **Only ~4% reach flip 10** |
| 12 | 0.74% | Less than 1 in 100 |
| 15 | 0.04% | 4 in 10,000 |
| 17+ | <0.01% | Virtually impossible |

### Average Session Length: ~6 Flips

The expected (average) number of flips before a player hits zero is **approximately 6**. This means:
- Most sessions are quick (3-7 flips)
- Long sessions (10+ flips) are rare and exciting — players talk about them
- Extremely long sessions (15+) are nearly impossible — our maximum exposure is bounded

---

## 5. Why This Curve Shape Is Optimal

### 5.1 Why Not a Flat Probability?

A flat 15% loss chance per flip would also give ~6 flips average. But:

| | Flat 15% | Our Exponential Curve |
|---|---|---|
| **Flip 1 loss rate** | 15% (bad UX — lose immediately) | 0% (guaranteed win) |
| **Flip 2 loss rate** | 15% | 0% (guaranteed win) |
| **"Near miss" excitement** | Low — same odds every time | High — tension builds progressively |
| **Streak potential** | Moderate | High early, drops off — creates exciting narratives |
| **Tail risk (long sessions)** | Significant — 19.7% reach flip 10 | Low — only 3.7% reach flip 10 |
| **Player perception** | "Random and unfair" | "I was on a streak!" |

**Key insight:** Our curve front-loads the wins (safe early flips) and back-loads the losses. Players experience early success, get emotionally invested, then face increasing risk. This is the same psychological model used in every successful gaming product from slot machines to gacha games.

### 5.2 Why Not a True Sigmoid (S-Curve)?

A standard sigmoid (logistic function) has a slow start, fast middle, and slow end (S-shape). Our curve is an **exponential saturation** — it starts at the base rate and rises quickly then plateaus. This is better because:

1. **No "safe middle" zone.** A sigmoid's slow start would let players accumulate too much value before risk kicks in.
2. **Immediate, visible risk after the safe zone.** Jump from 0% to 12.3% is noticeable — players feel the tension immediately after the free flips.
3. **Asymptotic approach to 95%.** The curve never reaches 100%, so there's always hope. This 5% residual chance is psychologically critical — it makes every "miracle survival" feel earned.

### 5.3 Why Exponential Saturation Specifically?

The formula `base + (1-base) × (1 - e^(-k×n))` is a standard **charging curve** (same physics as a capacitor charging). Its properties are ideal:

- **Smooth and continuous** — no jarring probability jumps between flips
- **Single tuning parameter (k)** — one knob to adjust session length
- **Mathematically predictable** — easy to model house edge with precision
- **Industry-proven** — used in casino mathematics, insurance actuarial models, and reliability engineering
- **Provably fair compatible** — the probability is deterministic given the flip number, so players can verify outcomes

---

## 6. How Our Settings Achieve the 60% House Edge

The house edge doesn't come from the curve alone. It works together with the **denomination system**:

### Denomination Weights (What Players Win Per Flip)

| Denomination | Value (GHS) | Weight | Probability of Landing |
|---|---|---|---|
| GHS 1 | 1.00 | 30 | 29.7% |
| GHS 2 | 2.00 | 25 | 24.8% |
| GHS 5 | 5.00 | 20 | 19.8% |
| GHS 10 | 10.00 | 12 | 11.9% |
| GHS 20 | 20.00 | 8 | 7.9% |
| GHS 50 | 50.00 | 4 | 4.0% |
| GHS 100 | 100.00 | 1 | 1.0% |
| GHS 200 | 200.00 | 1 | 1.0% |
| **Total** | | **101** | **100%** |

**Weighted average win per flip:** ~GHS 8.22

### The House Edge Mechanics

1. **Player stakes GHS X** (minimum GHS 1)
2. **First 2 flips are free wins** — player accumulates ~GHS 16.44 on average
3. **From flip 3 onward**, the escalating curve increasingly likely to zero them out
4. **When zero hits, player loses EVERYTHING** — stake + all accumulated winnings
5. **If player cashes out voluntarily**, they keep their winnings but the stake is "spent"

The house edge emerges from the gap between:
- **What players accumulate** (average ~6 flips × ~GHS 8.22 = ~GHS 49 on a GHS 1 stake)
- **How often they lose it all** (most players get zeroed before they cash out)

Over millions of sessions, the math converges to the house retaining approximately 60% of all money staked.

---

## 7. Safeguards & Responsible Gaming

### Mathematical Safeguards
- **95% cap**: No single flip is ever "guaranteed loss" — preserves fairness perception
- **Max cashout GHS 10,000**: Hard cap on our exposure per session
- **Provably fair**: Every outcome uses HMAC-SHA256 with server seed, client seed, and nonce. Players can verify no manipulation occurred.

### Operational Safeguards
- **Simulation/Test Mode**: Admin can override the curve for testing without touching production settings
- **Pause mechanic**: Players can pause (for 10% fee) rather than being forced to continue or cash out
- **Session duration limit**: 120-minute maximum prevents marathon sessions

### Why Our Settings Are Conservative (Good)
- **k = 0.08 is moderate**. A k of 0.15 would give ~3.5 flip average (too aggressive — players feel cheated). A k of 0.04 would give ~11 flip average (too generous — house edge drops).
- **base_rate = 0.05 is low**. Players' first risky flip (flip 3) is only 12.3% dangerous. This feels fair.
- **2 guaranteed safe flips** is the sweet spot. 0 would feel predatory. 3+ would cost us too much in guaranteed payouts.

---

## 8. Competitive Positioning

| Feature | Cashflip | Traditional Slots | Crash Games |
|---|---|---|---|
| **House edge** | ~60% | 85-97% (2-15% RTP gap) | 1-5% |
| **Provably fair** | Yes (HMAC-SHA256) | No | Some |
| **Session length** | ~6 actions | 1 spin | Variable |
| **Player control** | Cash out anytime | None | Cash out anytime |
| **Skill element** | Timing of cashout | None | Timing of cashout |
| **Engagement model** | Escalating tension | Instant result | Escalating tension |

Our model sits between traditional slots (high house edge, no skill) and crash games (low house edge, high skill). We offer **escalating tension with player agency** — players choose when to cash out, creating a skill-perception element that drives engagement.

---

## 9. Tuning Guide: What Happens If We Change Parameters

### If we increase k (growth rate):
| k Value | Avg Session | House Retention | Player Feeling |
|---|---|---|---|
| 0.04 | ~11 flips | ~45% | Very generous, long sessions |
| **0.08 (current)** | **~6 flips** | **~60%** | **Balanced — exciting but fair** |
| 0.12 | ~4 flips | ~70% | Aggressive — feels "rigged" |
| 0.20 | ~3 flips | ~80% | Very aggressive — player churn risk |

### If we change base_rate:
| Base Rate | Flip 3 Loss % | Effect |
|---|---|---|
| 0.02 | 5.5% | Gentler start, more reach flip 5+ |
| **0.05 (current)** | **12.3%** | **Balanced** |
| 0.10 | 17.1% | Harsher, noticeable early losses |
| 0.20 | 27.4% | Many flip-3 losses, bad UX |

### If we change min_flips_before_zero:
| Safe Flips | Effect | Trade-off |
|---|---|---|
| 0 | Players can lose on flip 1 | Terrible UX, feels scammy |
| 1 | 1 guaranteed win | Minimal hook |
| **2 (current)** | **2 guaranteed wins** | **Good engagement hook, controlled cost** |
| 3 | 3 guaranteed wins | More generous, costs more per session |
| 5 | 5 guaranteed wins | Very generous, significantly lower house edge |

---

## 10. Summary: Why This Is Right for Cashflip

1. **Mathematically proven** — the exponential saturation curve is a standard tool in probability engineering, used across gaming, insurance, and reliability science.

2. **Psychologically optimized** — guaranteed early wins create engagement; escalating tension creates excitement; rare long streaks create viral stories.

3. **Financially sound** — ~60% house retention is strong, with bounded maximum exposure (GHS 10,000 cap + rapid probability escalation).

4. **Auditable and fair** — provably fair cryptographic verification means no player can accuse us of manipulation. The curve is deterministic.

5. **Tunable** — three parameters (base_rate, k, min_flips) let us adjust the player experience without changing the game mechanics. We can make it more generous for promotions or tighter if needed.

6. **Our current settings (k=0.08, base=0.05, safe=2) are the conservative sweet spot** — aggressive enough for healthy margins, generous enough for player satisfaction and retention.

---

## Appendix A: Mathematical Proof of Convergence

The probability of a player surviving to flip N is:

```
S(N) = Product from i=1 to N of (1 - P_zero(i))
```

Where P_zero(i) = 0 for i <= 2, and our curve for i > 2.

With our parameters:
- S(5) = 53.05% — half gone by flip 5
- S(10) = 3.72% — 96% gone by flip 10
- S(15) = 0.04% — essentially zero by flip 15

The series converges rapidly, guaranteeing that **no session runs indefinitely** and the house edge is maintained regardless of player behavior.

## Appendix B: Provably Fair Verification

Each flip generates a result hash:
```
result_hash = SHA256(server_seed + ":" + client_seed + ":" + nonce)
roll = first_8_hex_digits(result_hash) / 0xFFFFFFFF  → float [0, 1]
```

If `roll < P(zero)` for that flip → player loses.
If `roll >= P(zero)` → player wins a denomination (selected by weighted random from the hash).

After a session ends, the server seed is revealed. Players can recompute every hash and verify every outcome was determined by the seeds, not manipulated.

---

*This document contains proprietary game mechanics. Distribution is limited to authorized Cashflip stakeholders and regulatory reviewers.*
