#!/bin/bash
# ============================================================
# CashFlip Production Deploy Script
# ============================================================
# Runs from your local/staging machine. Uses Azure CLI to
# execute commands on all VMSS instances.
#
# USAGE:
#   ./scripts/deploy-prod.sh                         # Code update only (git pull + restart)
#   ./scripts/deploy-prod.sh --with-env FILE         # Code update + push .env file
#   ./scripts/deploy-prod.sh --init --env FILE       # First-time setup (SSH key + env + full deploy)
#   ./scripts/deploy-prod.sh --env-only FILE         # Push .env only, no code update
#   ./scripts/deploy-prod.sh --cert                  # Provision/renew SSL certs via certbot
#   ./scripts/deploy-prod.sh --status                # Check service status on all VMs
#   ./scripts/deploy-prod.sh --logs                  # Tail deploy logs from all VMs
#
# REQUIREMENTS:
#   - Azure CLI installed and logged in (az login)
#   - SSH deploy key at ~/.ssh/cashflip
# ============================================================

set -euo pipefail

# ---- Configuration ----
RESOURCE_GROUP="cashflip-prod-rg"
APP_VMSS="cashflip-app-vmss"
CELERY_VMSS="cashflip-celery-vmss"
SSH_KEY_PATH="$HOME/.ssh/cashflip"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[DEPLOY]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }
info() { echo -e "${BLUE}[INFO]${NC} $*"; }

# ---- Helper: Run command on all instances of a VMSS ----
run_on_vmss() {
    local vmss_name="$1"
    local script="$2"
    local label="$3"

    log "Getting instances for $vmss_name..."
    local instance_ids
    instance_ids=$(az vmss list-instances \
        --resource-group "$RESOURCE_GROUP" \
        --name "$vmss_name" \
        --query "[].instanceId" -o tsv 2>/dev/null)

    if [ -z "$instance_ids" ]; then
        warn "No instances found for $vmss_name"
        return 0
    fi

    local count=0
    local total
    total=$(echo "$instance_ids" | wc -l)

    for instance_id in $instance_ids; do
        count=$((count + 1))
        log "[$vmss_name] Instance $instance_id ($count/$total): $label"

        az vmss run-command invoke \
            --resource-group "$RESOURCE_GROUP" \
            --name "$vmss_name" \
            --instance-id "$instance_id" \
            --command-id RunShellScript \
            --scripts "$script" \
            --output json 2>&1 | jq -r '.value[0].message // "No output"' || {
                err "Failed on $vmss_name instance $instance_id"
            }

        log "[$vmss_name] Instance $instance_id: Done"
        echo ""
    done
}

# ---- Action: Push SSH deploy key to all VMs ----
push_ssh_key() {
    if [ ! -f "$SSH_KEY_PATH" ]; then
        err "SSH deploy key not found at $SSH_KEY_PATH"
        exit 1
    fi

    log "Pushing SSH deploy key to all VMs..."
    local key_b64
    key_b64=$(base64 -w 0 "$SSH_KEY_PATH")

    local script="
mkdir -p /opt/cashflip/.ssh
echo '$key_b64' | base64 -d > /opt/cashflip/.ssh/id_ed25519
chmod 600 /opt/cashflip/.ssh/id_ed25519
chown -R cashflip:cashflip /opt/cashflip/.ssh
echo 'SSH key installed'
"
    run_on_vmss "$APP_VMSS" "$script" "Push SSH key"
    run_on_vmss "$CELERY_VMSS" "$script" "Push SSH key"
    log "SSH keys deployed to all VMs"
}

# ---- Action: Push .env file to all VMs ----
push_env() {
    local env_file="$1"
    if [ ! -f "$env_file" ]; then
        err "Env file not found: $env_file"
        exit 1
    fi

    log "Pushing $env_file to all VMs as /opt/cashflip/.env"
    local env_b64
    env_b64=$(base64 -w 0 "$env_file")

    local script="
echo '$env_b64' | base64 -d > /opt/cashflip/.env
chown cashflip:cashflip /opt/cashflip/.env
chmod 600 /opt/cashflip/.env
echo '.env installed ($(wc -l < /opt/cashflip/.env) lines)'
"
    run_on_vmss "$APP_VMSS" "$script" "Push .env"
    run_on_vmss "$CELERY_VMSS" "$script" "Push .env"
    log "Environment file deployed to all VMs"
}

# ---- Action: Deploy code (git pull + restart) ----
deploy_code() {
    log "Deploying code to App VMs..."
    run_on_vmss "$APP_VMSS" "git config --global --add safe.directory /opt/cashflip/app 2>/dev/null; bash /opt/cashflip/deploy.sh" "Deploy code"

    log "Deploying code to Celery VMs..."
    run_on_vmss "$CELERY_VMSS" "git config --global --add safe.directory /opt/cashflip/app 2>/dev/null; bash /opt/cashflip/deploy.sh" "Deploy code"

    log "Code deployed to all VMs"
}

# ---- Action: Rebuild React admin console + restart pm2 ----
deploy_admin() {
    log "Rebuilding React admin console on App VMs..."
    local script="
export HOME=/root
cd /opt/cashflip/app/admin-dashboard
echo 'Installing deps...'
npm ci --production=false 2>&1 | tail -2
echo 'Building...'
npm run build 2>&1 | tail -3
pm2 restart cashflip-admin 2>&1 | tail -2
echo 'Admin console rebuilt and pm2 restarted'
"
    run_on_vmss "$APP_VMSS" "$script" "Rebuild admin console"
    log "Admin console rebuilt on all App VMs"
}

# ---- Action: Provision SSL certs ----
provision_certs() {
    log "Provisioning SSL certificates via certbot..."
    local script="
certbot --nginx \
    -d cashflip.amoano.com \
    -d manage.cashflip.amoano.com \
    --non-interactive --agree-tos \
    --email admin@amoano.com \
    --redirect || echo 'Certbot failed (may need DNS to propagate first)'
"
    run_on_vmss "$APP_VMSS" "$script" "SSL cert provisioning"
    log "SSL certificate provisioning complete"
}

# ---- Action: Check status ----
check_status() {
    log "Checking service status on all VMs..."

    local app_script="
echo '=== App VM Status ==='
echo 'cashflip.service:' \$(systemctl is-active cashflip.service)
echo 'nginx:' \$(systemctl is-active nginx)
echo 'Disk:' \$(df -h / | tail -1 | awk '{print \$5}')
echo 'Load:' \$(uptime | awk -F'load average:' '{print \$2}')
[ -f /opt/cashflip/logs/deploy.log ] && echo 'Last deploy:' \$(tail -1 /opt/cashflip/logs/deploy.log) || echo 'No deploy log'
"
    run_on_vmss "$APP_VMSS" "$app_script" "Status check"

    local celery_script="
echo '=== Celery VM Status ==='
echo 'cashflip-celery.service:' \$(systemctl is-active cashflip-celery.service)
echo 'Disk:' \$(df -h / | tail -1 | awk '{print \$5}')
echo 'Load:' \$(uptime | awk -F'load average:' '{print \$2}')
[ -f /opt/cashflip/logs/deploy.log ] && echo 'Last deploy:' \$(tail -1 /opt/cashflip/logs/deploy.log) || echo 'No deploy log'
"
    run_on_vmss "$CELERY_VMSS" "$celery_script" "Status check"
}

# ---- Action: Tail logs ----
tail_logs() {
    log "Deploy logs from all VMs..."
    run_on_vmss "$APP_VMSS" "tail -20 /opt/cashflip/logs/deploy.log 2>/dev/null || echo 'No deploy log'" "Logs"
    run_on_vmss "$CELERY_VMSS" "tail -20 /opt/cashflip/logs/deploy.log 2>/dev/null || echo 'No deploy log'" "Logs"
}

# ---- Usage ----
usage() {
    echo ""
    echo "CashFlip Production Deploy"
    echo "=========================="
    echo ""
    echo "Usage:"
    echo "  $0                            Code update only (git pull + restart)"
    echo "  $0 --with-env FILE            Code update + push .env file"
    echo "  $0 --init --env FILE          First-time: SSH key + env + full deploy"
    echo "  $0 --env-only FILE            Push .env file only (no code update)"
    echo "  $0 --admin                    Rebuild React admin console + restart pm2"
    echo "  $0 --cert                     Provision/renew SSL certificates"
    echo "  $0 --status                   Check service status on all VMs"
    echo "  $0 --logs                     View deploy logs from all VMs"
    echo "  $0 --help                     Show this help"
    echo ""
    echo "Examples:"
    echo "  # Initial production deploy"
    echo "  $0 --init --env terraform/production.env"
    echo ""
    echo "  # Regular code update (safe — does NOT touch .env)"
    echo "  $0"
    echo ""
    echo "  # Code update with env change"
    echo "  $0 --with-env terraform/production.env"
    echo ""
    echo "  # Code update + rebuild admin console"
    echo "  $0 --admin"
    echo ""
}

# ---- Preflight: Check Azure CLI ----
preflight() {
    if ! command -v az &>/dev/null; then
        err "Azure CLI (az) not found. Install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    fi

    # Check if logged in
    if ! az account show &>/dev/null; then
        err "Not logged in to Azure. Run: az login"
        exit 1
    fi

    info "Azure subscription: $(az account show --query name -o tsv)"
}

# ---- Main ----
main() {
    local mode="code"
    local env_file=""
    local rebuild_admin=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --init)
                mode="init"
                shift
                ;;
            --env|--with-env)
                if [ "$mode" != "init" ]; then
                    mode="code_and_env"
                fi
                shift
                env_file="$1"
                shift
                ;;
            --env-only)
                mode="env_only"
                shift
                env_file="$1"
                shift
                ;;
            --admin)
                rebuild_admin=true
                shift
                ;;
            --cert)
                mode="cert"
                shift
                ;;
            --status)
                mode="status"
                shift
                ;;
            --logs)
                mode="logs"
                shift
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                err "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    preflight

    echo ""
    log "============================================"
    log "  CashFlip Production Deploy"
    log "  Mode: $mode"
    log "  Resource Group: $RESOURCE_GROUP"
    log "============================================"
    echo ""

    case "$mode" in
        init)
            if [ -z "$env_file" ]; then
                err "Initial deploy requires --env FILE"
                echo "Usage: $0 --init --env terraform/production.env"
                exit 1
            fi
            log "=== INITIAL DEPLOY ==="
            push_ssh_key
            push_env "$env_file"
            deploy_code
            log ""
            warn "Next steps:"
            warn "  1. Point DNS: cashflip.amoano.com -> LB IP"
            warn "  2. Wait for DNS propagation (~5 min)"
            warn "  3. Run: $0 --cert"
            ;;
        code)
            log "=== CODE DEPLOY (env unchanged) ==="
            deploy_code
            if [ "$rebuild_admin" = true ]; then
                deploy_admin
            fi
            ;;
        code_and_env)
            log "=== CODE + ENV DEPLOY ==="
            push_env "$env_file"
            deploy_code
            if [ "$rebuild_admin" = true ]; then
                deploy_admin
            fi
            ;;
        env_only)
            if [ -z "$env_file" ]; then
                err "Need env file. Usage: $0 --env-only FILE"
                exit 1
            fi
            log "=== ENV ONLY (restarting services) ==="
            push_env "$env_file"
            # Restart services to pick up new env
            run_on_vmss "$APP_VMSS" "systemctl restart cashflip.service && echo 'Restarted'" "Restart app"
            run_on_vmss "$CELERY_VMSS" "systemctl restart cashflip-celery.service && echo 'Restarted'" "Restart celery"
            ;;
        cert)
            provision_certs
            ;;
        status)
            check_status
            ;;
        logs)
            tail_logs
            ;;
    esac

    echo ""
    log "============================================"
    log "  Deploy complete!"
    log "============================================"
}

main "$@"
