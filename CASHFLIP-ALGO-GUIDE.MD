# CashFlip Game Algorithm & System Guide


**Staff Training & Stakeholder Reference Document**
Version 1.0 — February 2026


---


## Table of Contents


1. [What is CashFlip?](#1-what-is-cashflip)
2. [How the Game Works (Player Experience)](#2-how-the-game-works)
3. [The Money Flow: Deposits, Stakes, GGR & Payouts](#3-the-money-flow)
4. [The Algorithm: How the House Always Wins](#4-the-algorithm)
5. [Stake Tiers & Denomination Levels](#5-stake-tiers)
6. [Payout Mode: Normal vs Boost](#6-payout-mode)
7. [GGR — Gross Gaming Revenue Explained](#7-ggr-explained)
8. [Provably Fair System](#8-provably-fair)
9. [Admin Controls (What You Can Configure)](#9-admin-controls)
10. [Key Numbers to Remember](#10-key-numbers)
11. [FAQ for Stakeholder Pitches](#11-faq)


---


## 1. What is CashFlip?


CashFlip is a **real-money note-flipping game** built for the African market. Players stake money and flip virtual Ghanaian Cedi banknotes. Each flip either reveals a winning denomination (adding to their balance) or a **ZERO note** (ending the game and losing everything).


The thrill is in the **risk-reward tension**: cash out early with small winnings, or keep flipping for bigger rewards — but risk losing it all.


**Business model:** The house retains **70%** of all money staked. Players receive back **30%** as winnings on average. This is our Gross Gaming Revenue (GGR).


---


## 2. How the Game Works (Player Experience)


### Step-by-Step Game Flow


```
DEPOSIT → STAKE → FLIP → FLIP → FLIP → CASH OUT or LOSE
```


1. **Deposit**: Player sends money via Mobile Money (MoMo) to their CashFlip wallet
2. **Choose Stake**: Player selects how much to risk (minimum GH₵50)
3. **Flip Notes**: Player taps to flip banknotes one at a time
  - Each winning flip adds money to a **running cashout balance**
  - The player sees their winnings growing on screen in real-time
4. **Decision Point** (after each flip):
  - **Cash Out**: Take the accumulated winnings and stop
  - **Flip Again**: Risk it all for more — but the next flip might be ZERO
5. **ZERO Note**: If a zero note appears, the player **loses everything** — the entire stake and all accumulated winnings are gone


### What the Player Sees


- The first 2 flips are **always safe** (no zero possible) — this hooks the player
- After flip 2, each flip has an **increasing chance** of being zero
- By flip 5-7, the odds are heavily against the player
- The player sees their **cashout balance growing** with each winning flip — this creates excitement and greed
- The running total display shows exactly how much they'd get if they cash out NOW


### Example Game Session


| Flip # | Note Shown | Payout (6% of 100 GHS stake) | Cashout Balance | Zero Chance |
|--------|-----------|------------------------------|-----------------|-------------|
| 1 | GH₵5 note | +GH₵5.00 | GH₵5.00 | 0% (safe) |
| 2 | GH₵2 note | +GH₵4.00 | GH₵9.00 | 0% (safe) |
| 3 | GH₵1 note | +GH₵3.00 | GH₵12.00 | 12.3% |
| 4 | GH₵5 note | +GH₵5.00 | GH₵17.00 | 19.0% |
| 5 | **ZERO** | Game Over | **GH₵0.00** | 25.3% |


*In this example, the player staked GH₵100 and lost it all. If they had cashed out after flip 4, they would have received GH₵17. The house keeps GH₵100 (full stake).*


> **Key insight for pitching**: The player ALWAYS sees their balance growing — it feels like they're winning even though the math guarantees the house profits over volume.


---


## 3. The Money Flow: Deposits, Stakes, GGR & Payouts


### The Complete Money Lifecycle


```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   DEPOSIT    │────▶│   WALLET    │────▶│    STAKE     │────▶│  GAME PLAY  │
│  (MoMo In)  │     │  (Balance)  │     │ (Locked $)   │     │  (Flipping) │
└─────────────┘     └─────────────┘     └──────────────┘     └──────┬──────┘
                         ▲                                         │
                         │                              ┌──────────┴──────────┐
                         │                              │                     │
                   ┌─────┴─────┐                  ┌─────▼─────┐       ┌──────▼──────┐
                   │  CASHOUT  │◀─────────────────│   WIN     │       │    LOSE     │
                   │ (30% avg) │                  │(Cash Out) │       │ (Hit Zero)  │
                   └─────┬─────┘                  └───────────┘       └──────┬──────┘
                         │                                                   │
                   ┌─────▼─────┐                                     ┌──────▼──────┐
                   │ WITHDRAW  │                                     │    GGR      │
                   │ (MoMo Out)│                                     │  (Revenue)  │
                   └───────────┘                                     └─────────────┘
```


### Critical Distinction: Deposits vs Revenue


| Term | Definition | Example |
|------|-----------|---------|
| **Deposit** | Money a player puts INTO their wallet | Player deposits GH₵100 via MoMo |
| **Wallet Balance** | Money sitting in the player's account — this is a **LIABILITY** (we owe it to them) | Player has GH₵100 in wallet, hasn't played |
| **Stake** | Money the player risks on a game session | Player starts a game with GH₵100 stake |
| **Payout / Cashout** | Money returned to the player after winning flips | Player cashes out GH₵30 after 4 flips |
| **GGR** | Stakes minus Payouts — this is our **ACTUAL REVENUE** | GH₵100 staked - GH₵30 cashed out = **GH₵70 GGR** |
| **Withdrawal** | Money a player takes OUT of their wallet to MoMo | Player withdraws GH₵30 to their MoMo |


### When Does Money Become Revenue?


```
Deposit of GH₵100 → GGR = GH₵0   (it's a liability, NOT revenue)
Player stakes GH₵100 → GGR = TBD  (money is now at risk)
Player loses (zero) → GGR = GH₵100 (full stake is our revenue)
Player cashes out GH₵30 → GGR = GH₵70 (stake minus payout)
```


**A deposit that hasn't been staked generates ZERO GGR.** The money is still the player's — they can withdraw it anytime.


---


## 4. The Algorithm: How the House Always Wins


### Two Levers Control the House Edge


The entire profitability of CashFlip is controlled by two mathematical levers:


**Lever 1: Payout Multiplier** — How much each winning flip pays
**Lever 2: Zero Probability Curve** — How quickly the game ends


```
Total Expected Payout = (Average Multiplier per Flip) × (Expected Number of Surviving Flips)
```


### Lever 1: Payout Multiplier


Each denomination has a **payout multiplier** — a percentage of the player's stake that gets added to their cashout balance per flip.


| Denomination | Normal Multiplier | What it means |
|-------------|-------------------|---------------|
| GH₵1 note | 3% | Flip pays 3% of stake (e.g. GH₵3 on GH₵100 stake) |
| GH₵2 note | 4% | Flip pays 4% of stake |
| GH₵5 note | 5% | Flip pays 5% of stake |
| GH₵10 note | 7% | Flip pays 7% of stake |
| GH₵20 note | 10% | Flip pays 10% of stake |
| GH₵50 note | 18% | Flip pays 18% of stake |
| GH₵100 note | 30% | Flip pays 30% of stake (rare, exciting!) |
| GH₵200 note | 50% | Flip pays 50% of stake (ultra rare, jackpot feel!) |


**Weighted average multiplier = 6.01% per flip**


Small denominations (GH₵1, GH₵2) appear most often. Big denominations (GH₵100, GH₵200) are very rare — but when they appear, they create excitement and the feeling of "almost winning big."


> **Important**: The face value of the note (GH₵1, GH₵5, etc.) is purely visual. The actual payout is always calculated as a percentage of the stake. This ensures the house edge is identical whether someone stakes GH₵50 or GH₵10,000.


### Lever 2: Zero Probability Curve


The chance of hitting a zero note **increases with every flip**:


| Flip # | Zero Probability | Survival Rate | What the player feels |
|--------|-----------------|---------------|----------------------|
| 1 | 0% | 100% | "Free flip! Easy money!" |
| 2 | 0% | 100% | "Two in a row! I'm on a roll!" |
| 3 | 12.3% | 87.7% | "Still going strong..." |
| 4 | 19.0% | 71.0% | "Hmm, should I cash out?" |
| 5 | 25.3% | 53.1% | "One more..." (50/50 territory) |
| 6 | 31.0% | 36.6% | "Just one more!" (getting greedy) |
| 7 | 36.3% | 23.3% | Very risky now |
| 8 | 41.2% | 13.7% | Unlikely to survive |
| 9 | 45.7% | 7.4% | Extremely unlikely |
| 10+ | 50%+ | <4% | Almost certain loss |


The formula: `P(zero) = 0.05 + 0.95 × (1 - e^(-0.08 × (flip - 2)))`


This creates a **beautiful engagement curve**:
- First 2 flips: Guaranteed safe → hooks the player
- Flips 3-5: Moderate risk → player sees money growing, feels confident
- Flips 6+: High risk → greed kicks in, most players lose here


### Putting It Together: The Math


```
Expected surviving flips: ~5
Average multiplier per flip: 6.01%
Expected total payout: 5 × 6.01% = 30.05% of stake
House edge: 100% - 30.05% = 69.95% ≈ 70%
```


**For every GH₵100 staked across all players, the house keeps GH₵70 on average.**


This is a mathematical certainty over volume — individual sessions vary wildly (some players win, some lose), but across thousands of sessions, the house ALWAYS converges to 70%.


---


## 5. Stake Tiers & Denomination Levels


To create a premium, leveled experience, different stake amounts see different banknote denominations:


| Tier | Stake Range | Notes Shown | Feel |
|------|------------|-------------|------|
| **Standard** | GH₵50 – GH₵200 | GH₵1, GH₵2, GH₵5 | Accessible, casual |
| **Premium** | GH₵200 – GH₵1,000 | GH₵10, GH₵20, GH₵50 | Mid-level excitement |
| **VIP** | GH₵1,000 – GH₵10,000 | GH₵50, GH₵100, GH₵200 | High roller, big notes flying |


**Why tiers matter:**
- A GH₵50 stake player sees small notes (GH₵1, GH₵2) — feels proportionate
- A GH₵5,000 stake player sees big notes (GH₵100, GH₵200) — feels premium and exciting
- The **actual payout is always the same percentage** regardless of tier — the house edge is identical


> **For stakeholders**: "Higher stakes unlock bigger denominations and a more premium visual experience, but the mathematical house edge remains constant at 70%."


---


## 6. Payout Mode: Normal vs Boost


The platform has two operating modes, switchable instantly from the admin dashboard:


### Normal Mode (Default)
- **Player payout: 30%** of stakes
- **House retention: 70%** of stakes
- Used during normal operations


### Boost Mode (Engagement Recovery)
- **Player payout: 40%** of stakes
- **House retention: 60%** of stakes
- Used when player participation drops — makes the game more generous to bring players back
- Multipliers are automatically increased by 1.33× across all denominations


| Denomination | Normal Multiplier | Boost Multiplier |
|-------------|-------------------|------------------|
| GH₵1 | 3% | 4% |
| GH₵2 | 4% | 5.5% |
| GH₵5 | 5% | 7% |
| GH₵10 | 7% | 9% |
| GH₵20 | 10% | 13% |
| GH₵50 | 18% | 24% |
| GH₵100 | 30% | 40% |
| GH₵200 | 50% | 65% |


**When to activate Boost Mode:**
- Daily active players drops below target
- New market launch (attract early adopters)
- Promotional campaigns
- Weekend/holiday engagement pushes


**When to switch back to Normal:**
- Player volume returns to healthy levels
- GGR margins need protection


---


## 7. GGR — Gross Gaming Revenue Explained


### The Formula


```
GGR = Total Stakes − Total Payouts
```


### Real-World Scenarios


**Scenario 1: Player deposits GH₵100 and does NOT play**
```
Deposits: GH₵100
Stakes: GH₵0
Payouts: GH₵0
GGR = GH₵0 − GH₵0 = GH₵0
The GH₵100 is a LIABILITY (we owe it to them). NOT revenue.
```


**Scenario 2: Player deposits GH₵100 and loses it all**
```
Deposits: GH₵100
Stakes: GH₵100 (player risked everything)
Payouts: GH₵0 (hit zero)
GGR = GH₵100 − GH₵0 = GH₵100
Full stake becomes revenue.
```


**Scenario 3: Player deposits GH₵100, stakes GH₵100, cashes out GH₵30**
```
Deposits: GH₵100
Stakes: GH₵100
Payouts: GH₵30 (player cashed out)
GGR = GH₵100 − GH₵30 = GH₵70
Player still has GH₵30 in wallet (can play again or withdraw).
```


**Scenario 4: Player deposits GH₵100, plays 3 times**
```
Game 1: Stakes GH₵50, loses (zero) → GGR = GH₵50
Game 2: Stakes GH₵30, cashes out GH₵12 → GGR = GH₵18
Game 3: Stakes GH₵20, loses (zero) → GGR = GH₵20
Total GGR = GH₵50 + GH₵18 + GH₵20 = GH₵88
Player wallet: GH₵12 remaining
```


### Expected GGR at Scale


| Daily Active Stakers | Avg Stake | Total Stakes | Expected GGR (70%) | Boost GGR (60%) |
|---------------------|-----------|-------------|--------------------|-----------------|
| 100 | GH₵100 | GH₵10,000 | **GH₵7,000** | GH₵6,000 |
| 500 | GH₵150 | GH₵75,000 | **GH₵52,500** | GH₵45,000 |
| 1,000 | GH₵200 | GH₵200,000 | **GH₵140,000** | GH₵120,000 |
| 5,000 | GH₵250 | GH₵1,250,000 | **GH₵875,000** | GH₵750,000 |


> **For stakeholders**: "Our algorithm mathematically guarantees GH₵70 of revenue for every GH₵100 staked. This is not gambling on outcomes — it's a statistical certainty at scale."


### What GGR Does NOT Include


- **Deposits**: Money sitting in wallets is a liability, not revenue
- **Withdrawals**: Money leaving the platform (reduces our cash, not our GGR)
- **Transaction fees**: MoMo charges are a separate cost line item


---


## 8. Provably Fair System


CashFlip uses a **provably fair** random number generation system. This is important for regulatory compliance and player trust.


### How It Works


1. **Before the game starts**: The server generates a secret "server seed" and gives the player a hash (fingerprint) of it
2. **The player provides their own "client seed"**: This ensures the server can't predict or manipulate outcomes after the fact
3. **Each flip**: The result is calculated by combining server seed + client seed + flip number
4. **After the game ends**: The server seed is revealed — the player can verify that every flip was pre-determined and fair


### Why This Matters


- **Players can't cheat**: Results are server-determined
- **We can't cheat**: Results are provably pre-determined before the game starts
- **Regulators love it**: Mathematical proof of fairness
- **No manipulation**: Even admin staff cannot alter individual game outcomes in real-time


> The house edge comes purely from the **mathematical probability curve**, not from manipulating individual outcomes.


---


## 9. Admin Controls (What You Can Configure)


Everything is configurable from the **React Admin Dashboard** at `console.cashflip.cash`:


### Settings → Game Tab
| Setting | What it does | Current Value |
|---------|-------------|---------------|
| House Edge % | Target house retention | 70% |
| Min Stake | Minimum amount to play | GH₵50 |
| Min Deposit | Minimum deposit amount | GH₵50 |
| Max Cashout | Maximum single session payout | GH₵10,000 |
| Payout Mode | Normal (70/30) or Boost (60/40) | Normal |
| Normal Payout Target | Player payout % in normal mode | 30% |
| Boost Payout Target | Player payout % in boost mode | 40% |
| Boost Multiplier Factor | How much to increase multipliers in boost | 1.33× |
| Zero Base Rate | Starting probability of zero | 5% |
| Zero Growth Rate | How fast zero probability increases | 0.08 |
| Min Flips Before Zero | Guaranteed safe flips | 2 |
| Min Flips Before Cashout | Prevent instant cashout exploit | 3 |
| Auto-Flip Timer | Seconds before idle auto-flip | 8 sec |


### Settings → Denominations Tab
- Edit payout multiplier for each denomination (normal AND boost)
- Edit weight (frequency) of each denomination
- Upload/change flip animation GIFs and face images
- Add or remove denominations


### Settings → Stake Tiers Tab
- Create/edit stake tiers (name, min/max stake range)
- Assign which denominations appear in each tier
- Enable/disable tiers


### Settings → Simulation Tab (Testing Only)
- Override game outcomes for demos and testing
- Force wins, force losses, set fixed probabilities
- Grant test balances to specific players
- **NEVER use in production for real players**


---


## 10. Key Numbers to Remember


### For Quick Reference


| Metric | Value |
|--------|-------|
| House edge (normal) | **70%** |
| Player payout (normal) | **30%** |
| House edge (boost) | **60%** |
| Player payout (boost) | **40%** |
| Min stake | **GH₵50** |
| Avg multiplier per flip | **6.01%** (normal) / **8.04%** (boost) |
| Expected flips before zero | **~5** |
| Guaranteed safe flips | **2** |
| Min flips before cashout | **3** |


### For Stakeholder Pitches


- "For every GH₵100 staked, the house retains GH₵70"
- "The algorithm is mathematically proven — not based on luck"
- "Player payouts are 30%, comparable to lottery (50%) but with higher engagement"
- "We can dynamically adjust to 40% payout during promotional periods"
- "The game is provably fair — verifiable by players and regulators"
- "Higher stakes unlock premium denomination tiers for a VIP experience"
- "All parameters are configurable in real-time from the admin console — no code changes needed"


---


## 11. FAQ for Stakeholder Pitches


**Q: What if a player gets lucky and wins big?**
A: Individual sessions can absolutely pay out more than the stake — that's what makes it exciting. But across thousands of sessions, the math guarantees the house retains 70%. A lucky player winning GH₵500 on a GH₵100 stake is offset by dozens of players who hit zero and lose their full stake.


**Q: Can the algorithm be manipulated by staff?**
A: No. The provably fair seed system means outcomes are mathematically pre-determined before each game starts. No one — not even system administrators — can change individual flip outcomes. The only thing admin can adjust is the overall probability parameters (which affect ALL future games equally).


**Q: What's the difference between CashFlip and a slot machine?**
A: CashFlip gives the player **agency** — they decide when to cash out. This creates emotional engagement (greed vs fear) that slots don't have. The running balance display makes players feel they're "winning" even though the math favors the house. Also, CashFlip is mobile-first, instant-play, and uses familiar currency denominations.


**Q: How do we make money if players stop playing?**
A: We don't — deposits sitting in wallets are liabilities, not revenue. Our revenue (GGR) only comes from active play. That's why the Boost mode exists: when participation drops, we increase payouts to 40% to attract players back. A smaller margin on higher volume is better than a large margin on zero volume.


**Q: Is this legal/regulated?**
A: CashFlip is designed for compliance with the Gaming Commission of Ghana. The provably fair system provides mathematical proof of fairness. The regulatory footer on the platform displays our commission details. House edge parameters can be adjusted to meet any regulatory requirements.


**Q: What happens if everyone decides to withdraw at once?**
A: Player wallet balances are backed by actual deposits. GGR (our profit) should be swept to an operational account regularly. Standard practice is to maintain a liquidity reserve equal to 2-3× daily withdrawal volume.


**Q: How does the Partner API work?**
A: Licensed partners integrate CashFlip into their own platforms using our API. They use a "seamless wallet" model — CashFlip never holds partner player funds. Instead, we debit/credit the partner's wallet system in real-time during gameplay. Partners earn a revenue share from the GGR generated by their players.


---


## Glossary


| Term | Definition |
|------|-----------|
| **GGR** | Gross Gaming Revenue = Total Stakes − Total Payouts |
| **Stake** | Amount a player risks to start a game session |
| **Payout / Cashout** | Amount returned to a player who cashes out before hitting zero |
| **Zero Note** | The loss card — ends the game, player loses entire stake and accumulated winnings |
| **Multiplier** | Percentage of stake paid out per winning flip (e.g. 6% = GH₵6 on GH₵100 stake) |
| **Weight** | How frequently a denomination appears (higher weight = more common) |
| **Stake Tier** | Groups of denominations shown at different stake levels (Standard/Premium/VIP) |
| **Boost Mode** | Promotional mode with higher payouts (40% vs 30%) to attract players |
| **Provably Fair** | Cryptographic system proving game outcomes are pre-determined and unmanipulable |
| **House Edge** | Percentage of stakes retained by the house (70% in normal mode) |
| **Wallet Balance** | Player's deposited funds — a liability until staked |
| **Locked Balance** | Funds currently at risk in an active game session |


---


*Document prepared for internal staff training and stakeholder presentations. Confidential — do not distribute externally without management approval.*



