# CASHFLIP — Staff & Marketing Guide

> **Version**: 2.0 | **Last Updated**: February 2026
> **Platform**: https://cashflip.amoano.com | **Admin Console**: https://console.cashflip.amoano.com

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Core Game Mechanics](#2-core-game-mechanics)
3. [Player Journey](#3-player-journey)
4. [Signature Game Features](#4-signature-game-features)
5. [Wallet & Payments](#5-wallet--payments)
6. [Achievement System](#6-achievement-system)
7. [Daily Bonus Wheel](#7-daily-bonus-wheel)
8. [Social & Engagement Features](#8-social--engagement-features)
9. [Admin Console](#9-admin-console)
10. [Partner / GaaS Platform](#10-partner--gaas-platform)
11. [OTP as a Service (OTPaaS)](#11-otp-as-a-service-otpaas)
12. [Technical Architecture](#12-technical-architecture)
13. [Marketing Talking Points](#13-marketing-talking-points)
14. [Glossary](#14-glossary)

---

## 1. Product Overview

**Cashflip** is a provably fair, real-money coin-flip game built for the African mobile-first market. Players stake real money, flip virtual banknotes, and cash out their winnings — all via mobile money.

### Value Proposition

| For Players | For Operators | For Partners (GaaS) |
|------------|---------------|---------------------|
| Instant mobile money deposits | Configurable house edge | White-label integration via API |
| Provably fair (verifiable) | Real-time analytics dashboard | Seamless wallet (debit/credit) |
| 3D casino-grade experience | Player management & KYC | Per-operator game config |
| Achievement badges & XP | Withdrawal approval pipeline | GGR reports & auto-settlements |
| Daily bonus wheel | Feature toggles (no deploy) | Branded loading experience |

### Key Numbers

- **House Edge**: Configurable (default 60%)
- **Min Stake**: Configurable (default GH₵1.00)
- **Max Cashout**: Configurable (default GH₵10,000)
- **Session Duration**: Up to 120 minutes
- **Provably Fair**: HMAC-SHA256, server seed + client seed + nonce

---

## 2. Core Game Mechanics

### 2.1 How a Game Session Works

```
Player stakes GH₵X
    ↓
Wallet debited → balance locked
    ↓
Player flips (repeatable)
    ↓
Each flip: random denomination (win) OR zero (loss)
    ↓
Win → amount added to cashout balance, player can flip again or cash out
Loss (zero) → game over, stake lost
    ↓
Cashout → cashout balance credited to wallet
```

### 2.2 Flip Probability System

The game uses an **escalating zero probability curve** to ensure house edge:

- **First N flips**: Guaranteed safe (configurable `min_flips_before_zero`, default 2)
- **After safe flips**: Zero probability increases with each flip using the formula: `P(zero) = base_rate + growth_rate * (flip_number - min_flips)^2`
- Default parameters: 5% base rate, 8% growth factor
- **Denomination selection**: Weighted random from configured denominations (e.g., GH₵0.50 through GH₵20.00)

### 2.3 Provably Fair Verification

Every session is cryptographically verifiable:

1. **Game Start**: Server generates a random `server_seed` and provides its SHA-256 hash to the player
2. **Each Flip**: Result = HMAC-SHA256(server_seed, client_seed:nonce:flip_number)
3. **Game End**: Full `server_seed` is revealed so player can verify every flip was fair
4. **Public Verification**: `/api/partner/v1/game/verify/{session_id}` endpoint available

### 2.4 Pause System

Players can pause mid-game:
- Costs a configurable percentage of current cashout balance (default 10%)
- Session saved and resumable later
- Prevents exploitation of "play forever" strategies

---

## 3. Player Journey

### 3.1 Registration & Login

1. Player opens the game URL on mobile browser
2. Enters phone number (Ghanaian format: 024XXXXXXX)
3. Receives 6-digit OTP via **WhatsApp** (primary) or **SMS** (fallback)
4. OTP verified, JWT tokens issued (60-min access, 7-day refresh)
5. Automatic token refresh keeps players logged in for up to 7 days without re-entering OTP

**Supported Auth Methods** (each toggleable in admin):
- Phone OTP via SMS (Twilio)
- Phone OTP via WhatsApp (Meta Business API with copy-code button)
- Google OAuth
- Facebook OAuth

### 3.2 Lobby Experience

After login, the player sees the **Lobby**:

- **Header Bar**: Player avatar, CASHFLIP logo, wallet balance (tappable for details)
- **Stake Selector**: Slider + quick-stake buttons (₵1, ₵5, ₵10, ₵20, ₵50)
- **Action Buttons**: Deposit, Withdraw, Transfer, Daily Bonus Wheel, Badges, History, Refer a Friend
- **Live Feed Ticker**: Real-time scrolling feed of other players' wins/losses (Aviator-style), showing masked player names, amount, and flip count
- **Zero Balance CTA**: When balance is zero, a beautiful overlay appears with blurred game background, animated coin stack, "Ready to Win?" headline, and deposit button with an ambient soothing sound

### 3.3 In-Game Experience

- **3D Banknote Flip**: Three.js rendered banknote card with branded CF logo on front and cedi symbol on back; flips with physics-based animation
- **HUD Display**: Current stake, flip count, running cashout balance, streak fire badge
- **Controls**: Central FLIP button, top-right CASHOUT button, Pause button, Lobby return
- **Result Animation**: Denomination value display, win/loss overlay with balance update, confetti particles

---

## 4. Signature Game Features

### 4.1 Confetti Particle System

Canvas-based particle effects triggered on game events:

- **Win Flip**: 35 gold/green confetti pieces burst from center with physics simulation (gravity, rotation, fade-out)
- **Cashout**: Massive 240-piece gold shower in 3 cascading waves over 1.5 seconds
- **Loss**: 15 subtle red shards scatter briefly
- **Badge Unlock**: 40 purple/gold/green particles
- Pure canvas 2D rendering with zero external dependencies

### 4.2 Streak Fire Badge

A visual streak counter displayed in the game HUD below the denomination display:

| Streak | Display | Visual Style |
|--------|---------|--------------|
| 2 wins | 🔥 x2 STREAK | Orange text |
| 3 wins | 🔥 x3 STREAK | Orange glow |
| 5 wins | 🔥🔥 x5 ON FIRE! | Red glow + pulse animation |
| 7+ wins | 🔥🔥🔥 x7 INFERNO! | Intense gradient + fast pulse |

Resets on loss or when starting a new game session.

### 4.3 Casino Sound Engine

All sounds are synthesized via Web Audio API at runtime — zero audio file downloads required:

| Event | Sound Profile | Character |
|-------|--------------|-----------|
| Flip | Triple coin-clink (square wave) | Quick, tactile |
| Win | C-E-G-C arpeggio (sine wave) | Satisfying major chord |
| Big Win | Extended arpeggio + high sustain | Celebratory |
| Loss | Descending sawtooth buzz | Subtle, not punishing |
| Cashout | 6-note rising cascade | Triumphant |
| Deposit CTA | C major 7th ambient chord (C-E-G-B) | Warm, soothing, inviting |
| Wheel Spin | Rising tick pattern | Anticipation builder |

AudioContext initializes on first user touch to comply with browser autoplay policies.

### 4.4 Haptic Feedback (Mobile)

Vibration patterns on supported mobile devices:

| Event | Pattern (ms) | Sensation |
|-------|-------------|-----------|
| Win | [30, 30, 60] | Light double-tap |
| Loss | [100, 50, 200] | Heavy buzz |
| Cashout | [50, 50, 50, 50, 100] | Celebration pattern |

### 4.5 Social Proof Toasts

Real-time "someone just won" notifications in the lobby:
- System polls the live feed every 8 seconds
- Shows sliding pill-shaped toast from top of screen
- Format: "Player*** just won GH₵150.00!"
- Minimum win amount threshold configurable in admin (default GH₵10)
- Creates urgency, FOMO, and validates game legitimacy to new players

### 4.6 Branded 3D Coin Face

The Three.js banknote uses dynamically generated **CanvasTexture** for premium visuals:
- **Front Face**: Gold radial gradient background, embossed "CF" monogram, "CASHFLIP" text, decorative stars
- **Back Face**: Dark green gradient, large gold ₵ cedi symbol, teal accent ring
- All rendered on HTML5 canvas — no external image files needed
- Makes screenshots and screen recordings instantly brand-recognizable

### 4.7 Zero-Balance Deposit CTA

When a player has no funds, instead of a blank screen:
- Game board remains visible but blurred behind a semi-transparent overlay
- Animated floating ₵ coin symbols
- "Ready to Win?" headline with dynamic minimum stake info
- Prominent green "Deposit Now" button
- A warm C-major-7th ambient chord plays once on overlay appearance (non-intrusive)

---

## 5. Wallet & Payments

### 5.1 Wallet Architecture

Each player has **one wallet per currency** with:
- **Balance**: Total funds in the wallet
- **Locked Balance**: Funds reserved for active game sessions (staked but not yet resolved)
- **Available Balance**: `balance - locked_balance` (what the player can withdraw or stake)

All wallet mutations are atomic database transactions to prevent race conditions.

### 5.2 Transaction Types

| Type | Code | Description | Direction |
|------|------|-------------|-----------|
| Deposit | `deposit` | Mobile money deposit confirmed | Credit (+) |
| Withdrawal | `withdrawal` | Mobile money cashout approved | Debit (-) |
| Game Stake | `stake` | Locked when starting a game | Debit (-) |
| Game Cashout | `cashout` | Returned on player cashout | Credit (+) |
| Game Win | `win` | Flip win credited | Credit (+) |
| Pause Fee | `pause_fee` | Cost to pause a session | Debit (-) |
| P2P Transfer Out | `transfer_out` | Sent to another player | Debit (-) |
| P2P Transfer In | `transfer_in` | Received from another player | Credit (+) |
| Referral Bonus | `referral_bonus` | Reward for referring friends | Credit (+) |
| Ad/Daily Bonus | `ad_bonus` | Daily wheel or ad reward | Credit (+) |
| Admin Credit | `admin_credit` | Manual credit by admin | Credit (+) |
| Admin Debit | `admin_debit` | Manual debit by admin | Debit (-) |

Every transaction records: UUID, `balance_before`, `balance_after`, unique reference string, and freeform JSON metadata.

### 5.3 Deposits

- **Provider**: Paystack mobile money integration
- **Networks**: MTN, Vodafone/Telecel, AirtelTigo (auto-detected from phone prefix)
- **Phone Verification**: Registered account holder name must match across all linked accounts
- **Minimum**: Configurable (default GH₵1.00)
- **Confirmation**: Real-time webhook from Paystack confirms deposit instantly
- **Reference Format**: `CF-DEP-{uuid}` (staging) / `CFP-DEP-{uuid}` (production)

### 5.4 Withdrawals

- **Provider**: Paystack transfers
- **Pipeline**: Player requests → Admin reviews → Approved (auto-paid) or Rejected (auto-refunded)
- **Admin Dashboard**: Shows all pending withdrawals with player details, amount, date, and one-click approve/reject
- **Rejection**: Automatically credits the amount back to the player's wallet
- **Reference Format**: `CF-PAY-{uuid}` (staging) / `CFP-PAY-{uuid}` (production)

### 5.5 Peer-to-Peer Transfers

- Transfer funds to any active Cashflip player by phone number
- **Limits**: Min GH₵1, Max GH₵500 per transfer
- **Atomic**: Double-entry bookkeeping (sender debit + receiver credit in one DB transaction)
- **Rate Limited**: Max 5 transfers per minute
- **Validation**: Cannot transfer to self; recipient must be an existing active player

### 5.6 Mobile Money Account Management

- Players register one or more mobile money accounts
- Name verification via Paystack resolve API: account holder name must **exactly match** (case-insensitive) across all registered accounts for fraud prevention
- Network auto-detected: 024/054/055 = MTN, 020/050 = Vodafone, 026/056 = AirtelTigo
- Primary account used for withdrawals

---

## 6. Achievement System

### 6.1 Full Badge Catalog

14 badges across multiple achievement categories:

**Getting Started**
| Badge | Emoji | Condition | XP |
|-------|-------|-----------|-----|
| First Win | 🎯 | Win your very first flip | 10 |
| First Deposit | 🏦 | Make your first deposit | 10 |

**Streak Achievements**
| Badge | Emoji | Condition | XP |
|-------|-------|-----------|-----|
| 3-Win Streak | 🔥 | Win 3 flips in a row in one session | 15 |
| 5-Win Streak | 💥 | Win 5 flips in a row in one session | 25 |
| 7-Win Streak | 🌋 | Win 7 flips in a row — INFERNO! | 50 |

**High Roller Achievements**
| Badge | Emoji | Condition | XP |
|-------|-------|-----------|-----|
| High Roller | 💎 | Stake GH₵100+ in a single game | 20 |
| Whale | 🐋 | Stake GH₵500+ in a single game | 50 |

**Cashout Achievements**
| Badge | Emoji | Condition | XP |
|-------|-------|-----------|-----|
| Big Cashout | 💰 | Cash out GH₵50+ in one session | 20 |
| Mega Cashout | 🤑 | Cash out GH₵200+ in one session | 40 |

**Milestone Achievements**
| Badge | Emoji | Condition | XP |
|-------|-------|-----------|-----|
| Flip Master | 🎰 | Complete 100 total flips across all sessions | 30 |
| Veteran | ⭐ | Play 50 game sessions | 35 |
| Daily Player | 📅 | Play 7 consecutive days | 30 |

**Special Achievements**
| Badge | Emoji | Condition | XP |
|-------|-------|-----------|-----|
| Lucky 7 | 🍀 | Win on exactly flip number 7 | 25 |
| Social Butterfly | 🦋 | Refer a friend who plays their first game | 20 |

### 6.2 Badge Notification

When a badge is earned mid-game or on cashout:
- A **purple/teal gradient pill** slides down from top of screen
- Shows badge emoji + "Badge Unlocked!" + badge name
- 40-piece confetti burst in purple/gold/green
- Big win sound effect plays
- Auto-dismisses after 4 seconds

### 6.3 Badges Modal

Accessible from lobby via the "Badges" button:
- **XP Progress Bar**: Shows total XP earned and badge count (e.g., "85 XP — 6/14 earned")
- **2-Column Grid**: All 14 badges displayed
- **Earned State**: Teal border highlight, checkmark icon, full color
- **Locked State**: Dimmed, lock icon, greyed out
- Each badge card shows: emoji, name, and description

### 6.4 How Badges Are Awarded

Badges are checked and awarded automatically:
- **After every flip**: Checks for streak badges, first win, lucky 7
- **After every cashout**: Checks for cashout amount badges, session milestones
- **Backend-driven**: `check_and_award_badges()` function runs server-side with try/catch to never crash the main flow
- **Idempotent**: Each badge can only be earned once per player (PlayerBadge unique constraint)

---

## 7. Daily Bonus Wheel

### 7.1 How It Works

1. Player taps "Daily Bonus" button in the lobby (glowing teal animation)
2. Modal opens with a colorful canvas-drawn wheel
3. If spin is available, player taps "SPIN!"
4. Wheel animates for 4 seconds with ease-out deceleration (realistic physics feel)
5. Pointer at top indicates winning segment
6. Won amount instantly credited to wallet as `ad_bonus` transaction type
7. 24-hour cooldown before next spin (shown as countdown timer)

### 7.2 Default Wheel Segments

| Segment | Value | Color | Weight (probability) |
|---------|-------|-------|---------------------|
| ₵0.20 | GH₵0.20 | Teal | 30 (highest chance) |
| ₵0.50 | GH₵0.50 | Green | 25 |
| ₵1.00 | GH₵1.00 | Gold | 20 |
| ₵2.00 | GH₵2.00 | Orange | 12 |
| ₵5.00 | GH₵5.00 | Red | 8 |
| ₵10.00 | GH₵10.00 | Purple | 4 (rarest) |

Weights are relative: a segment with weight 30 is 30/(30+25+20+12+8+4) = 30.3% likely.

### 7.3 Admin Configuration

All wheel parameters are editable from the Admin Console Settings > Daily Wheel tab:
- Enable/disable the entire wheel feature
- Cooldown period (hours between spins)
- Maximum spins per day
- Require deposit before spinning (toggle)
- Add/remove/edit segments: label, value, color (with color picker), weight
- Changes take effect immediately — no redeploy needed

---

## 8. Social & Engagement Features

### 8.1 Referral System

- Each player gets a unique referral code
- Share via WhatsApp, SMS, or copy link
- Referrer earns bonus when referee makes their first deposit
- Referral bonus configurable in admin

### 8.2 Live Feed

- Real-time scrolling ticker in the lobby showing recent game results
- Each entry: masked player name (e.g., "Bol**an"), win/loss, amount, flip count
- Supports simulated feed data for demo/pitching (configurable in admin with fake entries)
- Creates casino-floor atmosphere on mobile

### 8.3 Player Profile & Stats

Each player has a persistent profile tracking:
- Total games played, won, and lost
- Highest single cashout amount
- Best win streak
- Current player level
- Lifetime deposits and withdrawals
- Total flips across all sessions

---

## 9. Admin Console

### 9.1 Overview

A full React SPA dashboard at `console.cashflip.amoano.com`:
- **Stack**: React + Vite + Tailwind CSS v4 + Recharts
- **Auth**: Same JWT system as the game (staff/superuser accounts)
- **API Backend**: Django `dashboard` app at `/api/admin/v1/`

### 9.2 Dashboard Pages

| Page | Description |
|------|-------------|
| **Dashboard** | KPI cards (revenue, players, sessions, GGR), daily revenue chart, daily player chart |
| **Players** | Searchable player list, detail view with profile stats and transaction history |
| **Sessions** | Game session browser with status filters, flip replay |
| **Transactions** | Wallet transaction log with type/status filters |
| **Finance** | Deposit/withdrawal totals, pending withdrawals with approve/reject, GGR breakdown, daily P&L chart, transaction type filter, period selector (7d/30d/90d), sortable columns |
| **Partners** | Partner operator management, API key provisioning, branding, game config |
| **Analytics** | Enhanced analytics: total sessions, win rate, top 10 players by stake volume, deposit/withdrawal volumes, daily finance chart, top denomination breakdown, retention metrics |
| **Roles & Access** | Staff role management with granular permissions |
| **Settings** | 5-tab settings panel (see below) |

### 9.3 Settings Tabs

**Auth Tab**: Toggle SMS OTP, WhatsApp OTP, Google OAuth, Facebook OAuth. Set OTP expiry and max attempts.

**Game Tab**: House edge %, min deposit, max cashout, min stake, pause cost %, zero base rate, zero growth rate, min flips before zero, session duration. Simulated feed toggle and feed data editor.

**Features Tab**: 8 toggle switches for game features:
- Achievement Badges
- Daily Bonus Wheel
- Casino Sounds
- Haptic Feedback
- Social Proof Toasts
- Streak Fire Badge
- Confetti Particles
- Deposit CTA Sound
- Social proof minimum amount threshold

**Daily Wheel Tab**: Enable/disable wheel, cooldown hours, max spins/day, require deposit checkbox, segment editor with inline color picker, value, weight, add/remove buttons.

**Simulation Tab**: Create/edit/delete test configs that override game outcomes for QA:
- Modes: Always Win, Always Lose, Force Zero at Flip N, Fixed Probability, Win Streak Then Lose
- Target all players or specific players
- Override min stake / max cashout
- Grant test balance
- Auto-disable after N sessions

### 9.4 Finance Dashboard Details

The finance page provides:
- **All-Time Totals**: Total deposits, total withdrawals, net revenue
- **Period Totals**: Deposits, withdrawals, GGR, GGR margin % for selected period
- **Pending Withdrawals**: List with player name, phone, amount, date — one-click approve/reject
- **Daily P&L Chart**: Stacked area chart showing deposits, withdrawals, GGR, and net flow per day
- **Transaction Filters**: Filter by type (deposits only, withdrawals only, all) and sort by amount or date
- **Period Selector**: 7 days, 30 days, 90 days, or all-time

### 9.5 Analytics Dashboard Details

- **Summary Cards**: Total GGR, total stakes, total payouts, average session value, average flips per session, total sessions, won/lost sessions, win rate, house edge actual %, 7-day retention rate, deposit/withdrawal volumes and counts
- **Daily Revenue Chart**: Revenue and GGR per day (line/area chart via Recharts)
- **Daily Players Chart**: New players vs active players per day
- **Daily Finance Chart**: Deposits vs withdrawals per day
- **Top 10 Players Table**: Phone, total staked, total won, GGR contribution, game count
- **Top Denominations**: Most frequently landed denominations with counts

---

## 10. Partner / GaaS Platform

### 10.1 Overview

Cashflip operates as a **Games-as-a-Service (GaaS)** platform. External operators (e.g., Elitebet, betting platforms) can integrate Cashflip into their own apps via REST API.

### 10.2 Integration Model

```
Operator App  ←→  Cashflip API  ←→  Game Engine
     ↑                                    ↓
Player's wallet                    Provably fair results
(operator-managed)                 (Cashflip-managed)
```

### 10.3 Seamless Wallet Protocol

Cashflip does NOT hold operator player funds. Instead:
1. **Game Start**: Cashflip calls operator's `debit_url` to deduct stake from player
2. **Game Win/Cashout**: Cashflip calls operator's `credit_url` to credit winnings
3. **Failure**: Cashflip calls operator's `rollback_url` to reverse failed debits

### 10.4 Partner API Endpoints

All endpoints at `/api/partner/v1/` with HMAC-SHA256 authentication:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `players/auth` | POST | Register or authenticate operator player |
| `game/config` | GET | Get operator's game configuration |
| `game/start` | POST | Start a new game session (triggers debit) |
| `game/flip` | POST | Execute a flip in active session |
| `game/cashout` | POST | Cash out session (triggers credit) |
| `game/state/{id}` | GET | Get current session state |
| `game/history/{player}` | GET | Get player's game history |
| `game/verify/{id}` | GET | Verify session fairness (provably fair) |
| `reports/ggr` | GET | GGR report for date range |
| `reports/sessions` | GET | Session report with details |
| `settlements/` | GET | Settlement history |
| `webhooks/configure` | POST | Configure webhook URL and events |

### 10.5 Authentication

All requests signed with HMAC-SHA256:
- **X-API-Key**: Public key (format: `cf_live_xxxx`)
- **X-Signature**: HMAC-SHA256(request_body, api_secret)
- **X-Timestamp** (optional): Unix timestamp for replay protection
- API keys managed in admin console per partner

### 10.6 Per-Operator Configuration

Each operator can have custom:
- Currency and denominations
- House edge percentage
- Min/max stake limits
- Max cashout
- Zero probability curve parameters
- Session duration limits
- Commission rate (Cashflip's cut of GGR)
- Settlement frequency (daily/weekly/monthly)
- Custom branding (logo, colors, loading animation)

### 10.7 Webhooks

Operators receive real-time webhooks for events:
- `game.started` — new session opened
- `game.completed` — session ended (win or loss)
- `game.cashout` — player cashed out
- `settlement.generated` — new settlement ready

Webhook delivery with retry and logging.

### 10.8 Settlements

Automatic settlement generation:
- Calculates GGR (stakes - payouts) per period
- Applies commission percentage
- Generates settlement record with breakdown
- Configurable frequency: daily, weekly, monthly
- Minimum settlement threshold

---

## 11. OTP as a Service (OTPaaS)

*(New product — spun off from Cashflip's production-proven auth system)*

Cashflip's WhatsApp OTP infrastructure is offered as a standalone API service for external developers and businesses. See separate OTPaaS documentation for full details.

### 11.1 Key Capabilities

- WhatsApp OTP delivery via Meta Business API
- SMS OTP fallback via Twilio
- Whitelabel sender ID (premium tier)
- Per-client rate limiting and configuration
- Usage-based billing with tiered pricing
- Full delivery analytics and logs

---

## 12. Technical Architecture

### 12.1 Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.2 + Django REST Framework |
| Database | PostgreSQL (Azure Flexible Server in prod) |
| Cache/Queue | Redis (Azure Redis Premium in prod) |
| Task Queue | Celery (async OTP delivery, settlements, webhooks) |
| Web Server | Gunicorn + Nginx |
| Frontend Game | Vanilla JS + Three.js (3D) + Canvas (2D) + Web Audio API |
| Admin Console | React + Vite + Tailwind CSS v4 + Recharts |
| Payments | Paystack (mobile money) |
| OTP Channels | Meta WhatsApp Business API + Twilio SMS |
| Infrastructure | Azure (2 app VMs, 1 Celery VM, load balancer, Bastion) |
| CI/CD | Git push + deploy script |

### 12.2 Django Apps

| App | Purpose |
|-----|---------|
| `accounts` | Player model, OTP auth, JWT, social auth, profiles |
| `game` | Game engine, sessions, flips, denominations, config, badges, daily wheel, features |
| `wallet` | Wallet model, transactions, balance management |
| `payments` | Paystack integration, deposits, withdrawals, mobile money accounts |
| `partner` | GaaS operator integration, HMAC auth, seamless wallet, settlements |
| `dashboard` | Admin API (players, sessions, finance, analytics, settings, roles) |
| `referrals` | Referral codes, tracking, bonus distribution |
| `ads` | Ad integration and bonus system |
| `analytics` | Event tracking and aggregation |

### 12.3 Security

- JWT authentication with 60-min access / 7-day refresh tokens
- HMAC-SHA256 for partner API authentication
- Atomic database transactions for all wallet operations
- Rate limiting on OTP requests (6 per phone per hour)
- IP whitelisting for partner API keys
- CSRF protection disabled for API (JWT-only)
- Admin restricted to staff/superuser accounts
- SSL/TLS everywhere (Let's Encrypt)

---

## 13. Marketing Talking Points

### For Player Acquisition

- **"Your phone is your casino"** — No app download, works in any mobile browser
- **"Every flip is provably fair"** — Cryptographic proof, not just trust
- **"Win badges, earn XP"** — Gamification keeps players engaged beyond just money
- **"Free daily spin"** — Come back every day for a chance to win up to ₵10
- **"Send money to friends"** — Built-in P2P transfers, not just a game
- **"Deposit in 10 seconds"** — Mobile money, no bank account needed

### For Operator Partners

- **"Add a casino game in one API call"** — Full game engine as a service
- **"Your players, your wallet"** — Seamless wallet integration, you keep control
- **"Configure everything"** — House edge, stakes, denominations, branding — all customizable
- **"Provably fair = trust"** — Reduce player disputes with cryptographic verification
- **"Auto-settlements"** — GGR calculated and settled automatically

### For Investors

- **Proven unit economics**: Configurable house edge (default 60%) ensures profitability
- **Platform play**: GaaS model multiplies revenue through operator partnerships
- **African mobile-first**: Built specifically for mobile money markets
- **Low CAC**: WhatsApp OTP onboarding + daily bonus wheel drives organic retention
- **New revenue stream**: OTPaaS monetizes existing WhatsApp infrastructure

---

## 14. Glossary

| Term | Definition |
|------|-----------|
| **GGR** | Gross Gaming Revenue = total stakes minus total payouts |
| **House Edge** | Percentage of stakes retained by the house over time |
| **Zero** | The loss outcome in a flip — player loses entire stake |
| **Denomination** | The value shown on a winning flip (e.g., ₵5.00) |
| **Cashout Balance** | Accumulated winnings in a session that can be cashed out |
| **Locked Balance** | Wallet funds reserved for an active game session |
| **Provably Fair** | System where game outcomes can be cryptographically verified |
| **Server Seed** | Secret random string used to generate flip outcomes |
| **Client Seed** | Player-provided string mixed into outcome generation |
| **Nonce** | Counter incremented with each flip for unique outcomes |
| **Seamless Wallet** | Integration model where Cashflip calls operator's debit/credit APIs |
| **HMAC** | Hash-based Message Authentication Code for API request signing |
| **GaaS** | Games as a Service — licensing game engine to operators |
| **OTPaaS** | OTP as a Service — WhatsApp/SMS verification API for third parties |
| **Settlement** | Periodic financial reconciliation between Cashflip and operator |
| **XP** | Experience points earned by unlocking badges |

---

*This document is confidential and intended for Cashflip staff, partners, and authorized stakeholders only.*
