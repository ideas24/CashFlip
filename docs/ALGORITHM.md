# CashFlip Game Algorithm — Technical & Business Document

**Version:** 2.0 | **Date:** February 2026 | **Status:** Production

---

## 1. How It Works (Non-Technical)

### The Game in Plain English

CashFlip is a **luck-based cash game** where players stake real money and flip virtual banknotes. Each flip reveals a denomination that adds to their running balance. Players can **cash out at any time** to collect their winnings, but if they flip a **ZERO**, they lose everything — their stake and all accumulated winnings.

**Player Flow:**
1. Player deposits money into their wallet (Mobile Money / bank transfer)
2. Player chooses a stake amount (e.g., GH₵5)
3. Player starts flipping — each flip adds a percentage of their stake to their balance
4. Player decides each round: **flip again** (risk it) or **cash out** (keep winnings)
5. If a ZERO appears → game over, player loses their entire stake
6. The longer they play, the higher the chance of hitting ZERO

### Why Players Love It
- **Simple to understand** — flip and win, or hit zero and lose
- **Addictive tension** — "just one more flip" psychology
- **Visual excitement** — real Cedi banknote animations make wins feel tangible
- **Control illusion** — players choose when to stop (but math favors the house)

### Why It's Profitable
- On average, players receive back ~40% of their stake before hitting ZERO
- **The house keeps ~60%** of all money staked over time
- The "cash out" option creates a psychological trap — players often push for more

---

## 2. The Algorithm (Technical)

### 2.1 Core Mechanics

#### Provably Fair RNG
Every flip uses a **provably fair** random number generator:

```
result_hash = HMAC-SHA256(server_seed, f"{session_id}:{flip_number}:{client_seed}")
roll = first_8_hex_chars_of(result_hash) → float between 0.0 and 1.0
```

- **Server seed**: Generated per session, hashed and shown to player before game starts
- **Client seed**: Optional player-provided seed for additional randomness
- **Verification**: After game ends, server seed is revealed so player can verify every flip

#### Zero Probability (Loss Curve)
The probability of flipping a ZERO increases with each flip:

```
P(zero) = base_rate + (1 - base_rate) × (1 - e^(-k × adjusted_flip))
```

Where:
- `base_rate` = 0.05 (5% — starting probability after safe flips)
- `k` = 0.08 (growth rate — how fast probability climbs)
- `adjusted_flip` = flip_number - min_flips_before_zero
- `min_flips_before_zero` = 2 (guaranteed safe flips)
- Maximum cap: 95% (never 100% guaranteed loss)

**Probability Table (default settings):**

| Flip # | Zero Probability | Cumulative Survival |
|--------|-----------------|---------------------|
| 1      | 0% (safe)       | 100%                |
| 2      | 0% (safe)       | 100%                |
| 3      | 5.0%            | 95.0%               |
| 4      | 12.2%           | 83.4%               |
| 5      | 18.8%           | 67.7%               |
| 6      | 24.7%           | 51.0%               |
| 7      | 30.0%           | 35.7%               |
| 8      | 34.8%           | 23.3%               |
| 9      | 39.0%           | 14.2%               |
| 10     | 42.8%           | 8.1%                |
| 15     | 56.8%           | 0.8%                |

**Key insight:** By flip 7, only ~36% of players survive. By flip 10, only ~8%.

#### Denomination Selection & Payout
When a flip is NOT zero, a denomination is selected:

1. **Weighted random selection** from active denominations (each has a `weight`)
2. **Payout calculation**: `payout = stake × (denomination.payout_multiplier / 100)`

Example with GH₵10 stake:
- GH₵5 note (multiplier 8%) → player receives GH₵0.80
- GH₵20 note (multiplier 12%) → player receives GH₵1.20
- GH₵200 note (multiplier 25%) → player receives GH₵2.50

The **visual denomination** (GH₵5, GH₵20, GH₵200) is for excitement. The **actual payout** is always a percentage of the stake, ensuring consistent house edge regardless of stake level.

### 2.2 House Edge Calculation

**Expected Value per Session:**

```
EV = Σ (P(survive to flip N) × payout_at_flip_N) - stake

Avg payout per flip = Σ (weight_i / total_weight × multiplier_i / 100) × stake
Expected flips before zero ≈ 5 (with default settings)

EV ≈ (avg_multiplier% × expected_flips × stake) - stake
```

**With recommended settings:**
- Average payout multiplier: ~8% of stake per flip
- Expected flips before zero: ~5
- Expected total payout: 8% × 5 = 40% of stake
- **House edge: 60%**

**Comparison to other games:**
| Game | House Edge |
|------|-----------|
| CashFlip (default) | ~60% |
| Slot machines | 5-15% |
| Roulette | 2.7-5.3% |
| Sports betting | 5-10% |

CashFlip has a higher house edge, but the **perceived value** is high because:
- Players see real banknote denominations (GH₵200!) even when payout is small
- The "cash out anytime" mechanic makes players feel in control
- The escalating risk creates dopamine-driven "one more flip" behavior

### 2.3 Configuration Parameters

All parameters are **tunable from the admin dashboard** without code changes:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `zero_base_rate` | 0.05 | Starting zero probability (5%) |
| `zero_growth_rate` | 0.08 | How fast zero probability grows |
| `min_flips_before_zero` | 2 | Guaranteed safe flips |
| `house_edge_percent` | 60% | Target house retention |
| `payout_multiplier` | Per-denomination | % of stake added per flip |
| `weight` | Per-denomination | Relative selection frequency |
| `auto_flip_seconds` | 8 | Auto-flip if player idles |
| `pause_cost_percent` | 10% | Cost to pause a game |

### 2.4 Anti-Abuse Measures

- **Rate limiting**: 3 OTP requests/minute, 6/hour per phone
- **Session locking**: Stake is locked from wallet during play (prevents double-spend)
- **Provably fair**: All results verifiable post-game
- **Simulation configs**: Admin can override outcomes for testing (auto-disables after N sessions)
- **Max session duration**: 120 minutes (configurable)
- **Auto-flip timer**: Prevents indefinite idle sessions

---

## 3. Recommendations & Adjustments

### 3.1 Tuning House Edge (Lower for Growth)

For **launch/growth phase**, consider reducing house edge to attract players:

```
# More generous settings (35% house edge instead of 60%)
zero_base_rate: 0.03        # 3% base (was 5%)
zero_growth_rate: 0.05      # Slower growth (was 0.08)
min_flips_before_zero: 3    # 3 safe flips (was 2)
avg payout_multiplier: 13%  # Higher payouts (was 8%)
```

This gives players ~65% return, making the game feel more rewarding while still profitable.

### 3.2 Dynamic Difficulty (Future)

Consider implementing **player-segment pricing**:
- **New players (first 5 sessions)**: Lower house edge (30%) to hook them
- **Regular players**: Standard house edge (50-60%)
- **VIP/high rollers**: Slightly better odds (45%) to retain big spenders

This can be implemented via the existing `SimulatedGameConfig` system.

### 3.3 Jackpot/Bonus System (Future)

Add a **progressive jackpot** funded by a small % of each stake:
- 1% of every stake goes to jackpot pool
- Random trigger (0.01% chance per flip) awards the jackpot
- Creates massive excitement and social proof when someone wins

### 3.4 Denomination Strategy

**Current denominations (Ghana Cedi):**
| Denomination | Multiplier | Weight | Frequency |
|-------------|-----------|--------|-----------|
| GH₵0 (Zero) | 0% | 10 | ~11% |
| GH₵1 | 5% | 20 | ~22% |
| GH₵2 | 6% | 18 | ~20% |
| GH₵5 | 8% | 15 | ~17% |
| GH₵10 | 10% | 10 | ~11% |
| GH₵20 | 12% | 8 | ~9% |
| GH₵50 | 18% | 5 | ~6% |
| GH₵100 | 22% | 3 | ~3% |
| GH₵200 | 30% | 1 | ~1% |

**Recommended tuning:** Make high denominations (GH₵100, GH₵200) appear just often enough to create "near miss" excitement but rarely enough to maintain house edge.

### 3.5 Regulatory Considerations

- CashFlip is a **game of chance** and may require gaming licenses depending on jurisdiction
- The provably fair system provides transparency for regulatory compliance
- All game results, stakes, and payouts are fully auditable via the admin dashboard
- Player identity verification (KYC) should be implemented before scaling

---

## 4. Key Metrics to Monitor

| Metric | Target | Description |
|--------|--------|-------------|
| **GGR (Gross Gaming Revenue)** | 50-60% of stakes | Total stakes minus total payouts |
| **Average session length** | 5-8 flips | Higher = more engagement |
| **Cash-out rate** | 15-25% | % of sessions where player cashes out vs loses |
| **Return rate** | >60% | % of players who play again within 7 days |
| **Average stake** | Growing | Should increase as players gain confidence |
| **ARPU** | Growing | Average revenue per user per month |

---

## 5. Technical Architecture Summary

```
Player → Django REST API → Game Engine → PostgreSQL
                ↓
         Provably Fair RNG
         (HMAC-SHA256)
                ↓
         Zero Probability Curve
         (Exponential decay)
                ↓
         Denomination Selection
         (Weighted random, stake-based payout)
                ↓
         Wallet Transaction
         (Atomic, locked balance)
```

**Stack:** Django 5.2, PostgreSQL, Redis, Celery, Nginx, Azure VMSS
**Admin:** React + Vite dashboard with full CRUD for all game parameters
**Frontend:** Vanilla JS SPA with CSS animations + PNG flip sequences

---

*This document is confidential. For internal team use only.*
