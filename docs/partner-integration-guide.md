# CashFlip Partner API — Game-as-a-Service Integration Guide

**Version**: 2.0 | **Base URL**: `https://cashflip.cash/api/partner/v1/`  
**API Docs (Swagger)**: `https://cashflip.cash/api/docs/swagger/`  
**API Docs (ReDoc)**: `https://cashflip.cash/api/docs/`

---

## Overview

CashFlip offers a **Game-as-a-Service (GaaS)** API that allows licensed partners (betting platforms, gaming operators, fintech apps) to embed our provably fair coin-flip game directly into their platform.

**How it works:**
1. Partner registers via CashFlip admin portal → gets API keys
2. Partner's backend authenticates players and manages game sessions via our REST API
3. Player funds are managed via **Seamless Wallet** — CashFlip calls YOUR debit/credit endpoints
4. Partners earn commission on GGR (Gross Gaming Revenue)

---

## Authentication

All requests use **HMAC-SHA256** authentication with 3 headers:

| Header | Required | Description |
|--------|----------|-------------|
| `X-API-Key` | ✅ | Your public API key (starts with `cf_live_`) |
| `X-Signature` | ✅ | HMAC-SHA256 of the raw request body using your API secret |
| `X-Timestamp` | Optional | Unix timestamp (replay protection, 5-min window) |

### Signature Generation

```python
import hmac, hashlib, json, time

api_key = "cf_live_abc123..."
api_secret = "your_secret_hex..."

body = json.dumps({"ext_player_id": "player_001", "stake": "5.00", "currency": "GHS"})
signature = hmac.new(api_secret.encode(), body.encode(), hashlib.sha256).hexdigest()

headers = {
    "Content-Type": "application/json",
    "X-API-Key": api_key,
    "X-Signature": signature,
    "X-Timestamp": str(int(time.time())),
}
```

```javascript
// Node.js
const crypto = require('crypto');

const apiKey = 'cf_live_abc123...';
const apiSecret = 'your_secret_hex...';
const body = JSON.stringify({ ext_player_id: 'player_001', stake: '5.00', currency: 'GHS' });

const signature = crypto.createHmac('sha256', apiSecret).update(body).digest('hex');

const headers = {
  'Content-Type': 'application/json',
  'X-API-Key': apiKey,
  'X-Signature': signature,
  'X-Timestamp': Math.floor(Date.now() / 1000).toString(),
};
```

### IP Whitelisting (Optional)
You can restrict API access to specific IPs via the admin portal.

---

## Seamless Wallet (Debit/Credit)

CashFlip does **NOT** hold player funds. Instead, we call YOUR wallet endpoints:

### Your Endpoints (You Implement These)

| Endpoint | When Called | Purpose |
|----------|------------|---------|
| `debit_url` | Game Start | Deduct stake from player's balance |
| `credit_url` | Cashout | Credit winnings to player's balance |
| `rollback_url` | Debit failure recovery | Reverse a debit that can't be fulfilled |

### Debit Request (CashFlip → Your Server)

```json
POST {your_debit_url}
Authorization: Bearer {your_wallet_auth_token}
Content-Type: application/json

{
  "player_id": "your_ext_player_id",
  "amount": "5.00",
  "currency": "GHS",
  "tx_ref": "CF-DEB-A1B2C3D4E5F6G7H8",
  "type": "bet",
  "session_ref": "optional_your_session_ref"
}
```

**Expected Response (Success):**
```json
{
  "success": true,
  "balance": "95.00",
  "tx_id": "your_internal_tx_id"
}
```

**Expected Response (Insufficient Funds):**
```json
{
  "success": false,
  "error": "insufficient_funds",
  "balance": "3.00"
}
```

### Credit Request (CashFlip → Your Server)

```json
POST {your_credit_url}
Authorization: Bearer {your_wallet_auth_token}
Content-Type: application/json

{
  "player_id": "your_ext_player_id",
  "amount": "12.50",
  "currency": "GHS",
  "tx_ref": "CF-CRD-A1B2C3D4E5F6G7H8",
  "type": "win",
  "session_ref": "optional_your_session_ref"
}
```

### Rollback Request (CashFlip → Your Server)

```json
POST {your_rollback_url}
Authorization: Bearer {your_wallet_auth_token}
Content-Type: application/json

{
  "player_id": "your_ext_player_id",
  "amount": "5.00",
  "currency": "GHS",
  "tx_ref": "CF-RBK-A1B2C3D4E5F6G7H8",
  "original_tx_ref": "CF-DEB-A1B2C3D4E5F6G7H8",
  "type": "rollback"
}
```

**Important:** Always use `tx_ref` for idempotency. If you receive a duplicate `tx_ref`, return success without processing again.

---

## API Endpoints

### 1. Register/Authenticate Player

```
POST /api/partner/v1/players/auth
```

**Request:**
```json
{
  "ext_player_id": "player_12345",
  "display_name": "Kwame Asante"
}
```

**Response (201 Created / 200 Existing):**
```json
{
  "player_id": "uuid-internal-id",
  "ext_player_id": "player_12345",
  "display_name": "Kwame Asante",
  "created": true
}
```

### 2. Get Game Configuration

```
GET /api/partner/v1/game/config
```

**Response:**
```json
{
  "currency_code": "GHS",
  "currency_symbol": "GH₵",
  "house_edge_percent": "60.00",
  "min_stake": "1.00",
  "max_stake": "1000.00",
  "max_cashout": "10000.00",
  "pause_cost_percent": "10.00",
  "max_session_duration_minutes": 120
}
```

### 3. Start Game Session

```
POST /api/partner/v1/game/start
```

**Flow:** Validate stake → Call YOUR `debit_url` → Create session → Return session ID

**Request:**
```json
{
  "ext_player_id": "player_12345",
  "stake": "5.00",
  "currency": "GHS",
  "client_seed": "optional_client_seed",
  "ext_session_ref": "your_session_ref_001"
}
```

**Response (201):**
```json
{
  "session_id": "uuid-session-id",
  "server_seed_hash": "sha256_hash_for_provably_fair",
  "stake": "5.00",
  "currency": "GHS",
  "status": "active"
}
```

**Error (402 — Debit Failed):**
```json
{
  "error": "Debit failed",
  "detail": "Insufficient funds",
  "tx_ref": "CF-DEB-xxx"
}
```

### 4. Execute Flip

```
POST /api/partner/v1/game/flip
```

**Request:**
```json
{
  "session_id": "uuid-session-id"
}
```

**Response (Win):**
```json
{
  "success": true,
  "flip_number": 3,
  "value": "5.00",
  "is_zero": false,
  "cashout_balance": "15.00",
  "result_hash": "hmac_hash",
  "session_status": "active",
  "denomination": "5.00"
}
```

**Response (Loss — Zero):**
```json
{
  "success": true,
  "flip_number": 7,
  "value": "0.00",
  "is_zero": true,
  "cashout_balance": "0.00",
  "result_hash": "hmac_hash",
  "session_status": "lost"
}
```

### 5. Cash Out

```
POST /api/partner/v1/game/cashout
```

**Flow:** Close session → Call YOUR `credit_url` → Reveal server seed

**Request:**
```json
{
  "session_id": "uuid-session-id"
}
```

**Response:**
```json
{
  "session_id": "uuid-session-id",
  "cashout_amount": "15.00",
  "stake": "5.00",
  "flips": 5,
  "status": "cashed_out",
  "credit_status": "success",
  "credit_tx_ref": "CF-CRD-xxx",
  "server_seed": "full_server_seed_for_verification"
}
```

### 6. Get Session State

```
GET /api/partner/v1/game/state/{session_id}
```

Returns full session state including all flip results.

### 7. Get Player History

```
GET /api/partner/v1/game/history/{ext_player_id}
```

Returns last 50 game sessions for a player.

### 8. Verify Session (Provably Fair)

```
GET /api/partner/v1/game/verify/{session_id}
```

Returns server_seed, client_seed, and all flip hashes for cryptographic verification.

### 9. GGR Reports

```
GET /api/partner/v1/reports/ggr
```

Returns settlement records with total_bets, total_wins, GGR, commission, net_operator_amount.

### 10. Configure Webhooks

```
POST /api/partner/v1/webhooks/configure
```

**Request:**
```json
{
  "webhook_url": "https://your-server.com/cashflip/webhooks",
  "subscribed_events": ["game.started", "game.won", "game.lost", "game.flip"]
}
```

---

## Webhook Events

| Event | When | Key Fields |
|-------|------|------------|
| `game.started` | Session created | session_id, ext_player_id, stake, currency |
| `game.flip` | Each winning flip | session_id, flip_number, value, cashout_balance |
| `game.lost` | Player hits zero | session_id, flip_number, value=0 |
| `game.won` | Player cashes out | session_id, cashout_amount, credit_status |
| `settlement.ready` | Settlement generated | period, ggr, commission, net_amount |

---

## Complete Integration Flow

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  PARTNER APP    │       │   CASHFLIP API   │       │  PARTNER WALLET │
│  (Your Server)  │       │  (Our Server)    │       │  (Your Server)  │
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                          │
         │  1. POST /players/auth  │                          │
         │ ───────────────────────>│                          │
         │  { ext_player_id }      │                          │
         │ <───────────────────────│                          │
         │  { player_id }          │                          │
         │                         │                          │
         │  2. POST /game/start    │                          │
         │ ───────────────────────>│                          │
         │  { ext_player_id,       │  3. POST {debit_url}     │
         │    stake: 5.00 }        │ ────────────────────────>│
         │                         │  { player_id, amount,    │
         │                         │    tx_ref }              │
         │                         │ <────────────────────────│
         │                         │  { success: true }       │
         │ <───────────────────────│                          │
         │  { session_id,          │                          │
         │    server_seed_hash }   │                          │
         │                         │                          │
         │  4. POST /game/flip     │                          │
         │ ───────────────────────>│                          │
         │ <───────────────────────│                          │
         │  { value: 5.00,         │                          │
         │    is_zero: false,      │                          │
         │    cashout_balance: 5 } │                          │
         │                         │                          │
         │  5. POST /game/flip     │                          │
         │ ───────────────────────>│                          │
         │ <───────────────────────│                          │
         │  { value: 2.00,         │                          │
         │    cashout_balance: 7 } │                          │
         │                         │                          │
         │  6. POST /game/cashout  │                          │
         │ ───────────────────────>│                          │
         │                         │  7. POST {credit_url}    │
         │                         │ ────────────────────────>│
         │                         │  { player_id, amount:    │
         │                         │    7.00, tx_ref }        │
         │                         │ <────────────────────────│
         │                         │  { success: true }       │
         │ <───────────────────────│                          │
         │  { cashout_amount: 7,   │                          │
         │    server_seed }        │                          │
         │                         │                          │
```

---

## Settlement & Revenue Model

| Term | Definition |
|------|-----------|
| **Total Bets** | Sum of all stakes placed through your platform |
| **Total Wins** | Sum of all cashout amounts paid to players |
| **GGR** | Gross Gaming Revenue = Total Bets - Total Wins |
| **Commission** | Cashflip's cut (default 20% of GGR) |
| **Net Operator** | GGR - Commission = what you keep |

**Example:**
- Players bet GH₵100,000 total through your platform
- Players won GH₵40,000 in cashouts
- GGR = GH₵60,000
- Cashflip commission (20%) = GH₵12,000
- **Your net revenue = GH₵48,000**

Settlements are generated automatically (daily/weekly/monthly per config) and visible in the API and admin portal.

---

## Partner Onboarding Steps

1. **Apply** — Contact CashFlip for partner agreement
2. **Admin creates partner** — In CashFlip admin console → Partners → New
3. **Get API keys** — Admin generates `cf_live_*` key pair, shares securely
4. **Configure wallet URLs** — Partner provides `debit_url`, `credit_url`, `rollback_url`
5. **Set commission & settlement** — Configure % and frequency in admin portal
6. **Integration testing** — Use staging environment with test keys
7. **Go live** — Switch to production API keys, whitelist production IPs
8. **Monitor** — GGR reports, session logs, webhook delivery in admin portal

---

## Rate Limits

| Endpoint | Default Limit |
|----------|--------------|
| All endpoints | 120 req/min per API key |
| `/game/flip` | 30 req/min per session |
| `/game/start` | 10 req/min per player |

---

## Error Codes

| HTTP Status | Meaning |
|-------------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad request (invalid params) |
| 401 | Authentication failed (bad key/signature) |
| 402 | Payment required (debit failed) |
| 404 | Not found (player/session) |
| 429 | Rate limit exceeded |
| 500 | Server error |

---

## Per-Operator Customization

Each partner gets their own:
- **Game Config**: Custom house edge, stake limits, zero curve parameters
- **Branding**: Custom logo, colors, loading animation for iframe embed
- **Webhook Config**: Event subscriptions and delivery URL
- **API Keys**: Multiple keys with IP whitelisting and rate limits
- **Settlement Terms**: Custom commission %, settlement frequency, min amount
