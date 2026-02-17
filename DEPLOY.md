# CashFlip Production Deployment

## Architecture

```
                    ┌─────────────────────┐
                    │   Azure Load Balancer│
                    │   (TCP 80/443)       │
                    └────────┬────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │  App VM 1│  │  App VM 2│  │  App VM N│
        │  Nginx   │  │  Nginx   │  │  Nginx   │
        │  Gunicorn│  │  Gunicorn│  │  Gunicorn│
        └──────────┘  └──────────┘  └──────────┘
              │              │              │
              └──────┬───────┴──────┬───────┘
                     ▼              ▼
              ┌──────────┐  ┌──────────┐
              │ PostgreSQL│  │  Redis   │
              │ (Managed) │  │ (Managed)│
              └──────────┘  └──────────┘
                     ▲
              ┌──────┴───────┐
              │  Celery VM(s)│
              └──────────────┘
```

- **App VMs**: Nginx + Gunicorn (default: 2, scale to 5+)
- **Celery VMs**: Celery worker (default: 1, scale to 3+)
- **PostgreSQL**: Azure Flexible Server (HA, zone-redundant)
- **Redis**: Azure Cache for Redis (Premium, VNet-integrated)
- **Bastion**: SSH access to VMs (no public IPs on VMs)
- **Key Vault**: Secret storage

## Prerequisites

1. **Azure CLI** installed and logged in: `az login`
2. **Terraform** >= 1.0 installed
3. **SSH deploy key** at `~/.ssh/cashflip` (already configured for `cashflip:ideas24/CashFlip.git`)

## Step 1: Provision Infrastructure

```bash
cd terraform/

# Create terraform.tfvars from example
cp terraform.tfvars.example terraform.tfvars
# Edit: set admin_ssh_public_key and db_admin_password

terraform init
terraform plan    # Review what will be created
terraform apply   # Provision (~15-20 min)
```

## Step 2: Prepare Production .env

```bash
# Copy template
cp terraform/production.env.template terraform/production.env

# Fill in values from terraform output:
terraform -chdir=terraform output -raw database_url
terraform -chdir=terraform output -raw redis_url

# Edit terraform/production.env:
#   - Paste DATABASE_URL from output
#   - Paste REDIS_URL (use /0 for cache, /1 for broker, /2 for results)
#   - Generate new SECRET_KEY:  python3 -c "import secrets; print(secrets.token_hex(32))"
#   - Generate new JWT_SECRET_KEY: python3 -c "import secrets; print(secrets.token_hex(32))"
#   - Copy API keys from staging .env (Orchard, Paystack, WhatsApp, Twilio)
```

**Production prefixes are already set in the template:**
- `CFP-PS-` (Paystack) — staging uses `CF-PS-`
- `CFP-DEP-` (deposits) — staging uses `CF-DEP-`
- `CFP-PAY-` (payouts) — staging uses `CF-PAY-`

## Step 3: Initial Deploy

```bash
# Push SSH key + .env + clone repo + install + migrate + start services
./scripts/deploy-prod.sh --init --env terraform/production.env
```

## Step 4: DNS + SSL

```bash
# Update DNS A records to point to Load Balancer IP
LB_IP=$(terraform -chdir=terraform output -raw lb_public_ip)
echo "Point cashflip.amoano.com -> $LB_IP"
echo "Point manage.cashflip.amoano.com -> $LB_IP"

# Use the auto-generated DNS script (Porkbun API)
bash terraform/update_dns.sh

# Wait for DNS propagation (~5 min), then provision SSL
./scripts/deploy-prod.sh --cert
```

## Daily Operations

### Deploy code update (safe — does NOT touch .env)
```bash
./scripts/deploy-prod.sh
```
This runs on all VMs: `git pull` → `pip install` → `migrate` → `collectstatic` → restart.

### Deploy code + env update
```bash
./scripts/deploy-prod.sh --with-env terraform/production.env
```

### Push env only (no code change)
```bash
./scripts/deploy-prod.sh --env-only terraform/production.env
```

### Check VM status
```bash
./scripts/deploy-prod.sh --status
```

### View deploy logs
```bash
./scripts/deploy-prod.sh --logs
```

### Renew SSL certificates
```bash
./scripts/deploy-prod.sh --cert
```

### Scale up/down
```bash
# Edit terraform.tfvars: change app_vm_count or celery_vm_count
terraform -chdir=terraform apply

# Then deploy to new instances
./scripts/deploy-prod.sh --init --env terraform/production.env
```

## Environment Safety

| Command | Touches .env? | Use case |
|---------|--------------|----------|
| `deploy-prod.sh` | **NO** | Regular code updates |
| `deploy-prod.sh --with-env FILE` | **YES** | Code + config change |
| `deploy-prod.sh --env-only FILE` | **YES** | Config-only change |
| `deploy-prod.sh --init --env FILE` | **YES** | First-time setup |

**Staging `.env` is NEVER pushed to production.** The deploy script requires an explicit file path.

## Domains

| Domain | Environment | Points to |
|--------|-------------|-----------|
| `demo.cashflip.amoano.com` | Staging | `20.83.155.228` |
| `cashflip.amoano.com` | Production | LB public IP |
| `manage.cashflip.amoano.com` | Production Admin | LB public IP |
| `console.cashflip.amoano.com` | Production Console | LB public IP |

## Payment Routing (Proxy)

| Prefix | Environment | System |
|--------|-------------|--------|
| `CF-PS-` | Staging | CashFlip Paystack |
| `CF-DEP-` | Staging | CashFlip MoMo Deposit |
| `CF-PAY-` | Staging | CashFlip MoMo Payout |
| `CFP-PS-` | Production | CashFlip Paystack |
| `CFP-DEP-` | Production | CashFlip MoMo Deposit |
| `CFP-PAY-` | Production | CashFlip MoMo Payout |

## Troubleshooting

### SSH into a VM (via Bastion)
```bash
az network bastion ssh \
  --resource-group cashflip-prod-rg \
  --name cashflip-bastion \
  --target-resource-id <VM_RESOURCE_ID> \
  --auth-type ssh-key \
  --username cashflip_admin \
  --ssh-key ~/.ssh/cashflip
```

### Check service logs on a VM
```bash
# Via deploy script
./scripts/deploy-prod.sh --logs

# Or directly via az run-command
az vmss run-command invoke \
  --resource-group cashflip-prod-rg \
  --name cashflip-app-vmss \
  --instance-id 0 \
  --command-id RunShellScript \
  --scripts "journalctl -u cashflip.service --no-pager -n 50"
```

### Rollback
```bash
# SSH into VMs and revert to previous commit
az vmss run-command invoke \
  --resource-group cashflip-prod-rg \
  --name cashflip-app-vmss \
  --instance-id 0 \
  --command-id RunShellScript \
  --scripts "cd /opt/cashflip/app && git checkout HEAD~1 && systemctl restart cashflip.service"
```
