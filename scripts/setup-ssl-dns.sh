#!/bin/bash

# Setup SSL certificates for cashflip.cash using DNS-01 challenge via Porkbun API
# This avoids HTTP connectivity issues with Cloudflare proxy
# Usage: ./scripts/setup-ssl-dns.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
err() { echo -e "${RED}[ERROR]${NC} $1"; }

RESOURCE_GROUP="cashflip-prod-rg"
APP_VMSS="cashflip-app-vmss"

# Load Porkbun keys from production.env
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source <(grep PORKBUN "$SCRIPT_DIR/../terraform/production.env")

if [ -z "$PORKBUN_API_KEY" ] || [ -z "$PORKBUN_SECRET_KEY" ]; then
    err "PORKBUN_API_KEY and PORKBUN_SECRET_KEY not found in production.env"
    exit 1
fi

run_on_vmss() {
    local vmss_name="$1"
    local script="$2"
    local description="$3"
    
    log "Running on $vmss_name: $description"
    local instances=$(az vmss list-instances \
        --resource-group "$RESOURCE_GROUP" \
        --name "$vmss_name" \
        --query "[].instanceId" \
        --output tsv)
    
    for instance in $instances; do
        log "[$vmss_name] Instance $instance: $description"
        az vmss run-command invoke \
            --resource-group "$RESOURCE_GROUP" \
            --name "$vmss_name" \
            --instance-id "$instance" \
            --command-id 'RunShellScript' \
            --scripts "$script" \
            --output json 2>&1 | jq -r '.value[0].message' || {
            err "Failed on $vmss_name instance $instance"
        }
        log "[$vmss_name] Instance $instance: Done"
    done
}

# Install certbot-dns-porkbun and obtain certificate
ssl_script="
echo '=== Setting up SSL with DNS-01 challenge ==='

# Install certbot porkbun plugin
pip3 install certbot-dns-porkbun 2>&1 | tail -3

# Create Porkbun credentials file
mkdir -p /etc/letsencrypt
cat > /etc/letsencrypt/porkbun-credentials.ini << 'CREDS'
dns_porkbun_key = ${PORKBUN_API_KEY}
dns_porkbun_secret = ${PORKBUN_SECRET_KEY}
CREDS
chmod 600 /etc/letsencrypt/porkbun-credentials.ini

# Request certificate using DNS-01 challenge
certbot certonly \
    --authenticator dns-porkbun \
    --dns-porkbun-credentials /etc/letsencrypt/porkbun-credentials.ini \
    --dns-porkbun-propagation-seconds 60 \
    -d cashflip.cash \
    -d '*.cashflip.cash' \
    --email admin@amoano.com \
    --non-interactive \
    --agree-tos \
    --keep-until-expiring

if [ \$? -eq 0 ]; then
    echo 'Certificate obtained successfully!'
    
    # Update nginx configs to use new cert
    for conf in cashflip.cash manage.cashflip.cash console.cashflip.cash; do
        if [ -f /etc/nginx/sites-available/\$conf ]; then
            sudo sed -i 's|ssl_certificate /etc/letsencrypt/live/cashflip.amoano.com/fullchain.pem;|ssl_certificate /etc/letsencrypt/live/cashflip.cash/fullchain.pem;|g' /etc/nginx/sites-available/\$conf
            sudo sed -i 's|ssl_certificate_key /etc/letsencrypt/live/cashflip.amoano.com/privkey.pem;|ssl_certificate_key /etc/letsencrypt/live/cashflip.cash/privkey.pem;|g' /etc/nginx/sites-available/\$conf
            echo \"Updated \$conf to use cashflip.cash cert\"
        fi
    done
    
    # Remove options-ssl-nginx.conf include if cert doesn't have it
    # and add ssl_protocols/ciphers directly
    for conf in cashflip.cash manage.cashflip.cash console.cashflip.cash; do
        if [ -f /etc/nginx/sites-available/\$conf ]; then
            if [ ! -f /etc/letsencrypt/options-ssl-nginx.conf ]; then
                sudo sed -i '/include.*options-ssl-nginx.conf/d' /etc/nginx/sites-available/\$conf
                sudo sed -i '/ssl_dhparam/d' /etc/nginx/sites-available/\$conf
            fi
        fi
    done
    
    # Test and reload nginx
    sudo nginx -t && sudo systemctl reload nginx
    echo 'Nginx reloaded with new certificates'
    
    # Verify auto-renewal is configured
    echo 'Testing auto-renewal...'
    certbot renew --dry-run 2>&1 | tail -5
    
    # Add cron job for auto-renewal if not already present
    if ! crontab -l 2>/dev/null | grep -q 'certbot renew'; then
        (crontab -l 2>/dev/null; echo '0 3 * * * certbot renew --quiet --post-hook \"systemctl reload nginx\"') | crontab -
        echo 'Added cron job for auto-renewal at 3am daily'
    else
        echo 'Auto-renewal cron job already exists'
    fi
else
    echo 'Certificate request failed'
fi

echo '=== SSL setup complete ==='
"

log "Setting up SSL with DNS-01 challenge on App VMSS instances..."
log "This uses Porkbun API for DNS validation (no HTTP access needed)"
run_on_vmss "$APP_VMSS" "$ssl_script" "SSL via DNS-01"

log "SSL setup complete!"
echo ""
echo "Domains configured:"
echo "  - https://cashflip.cash (main app)"
echo "  - https://manage.cashflip.cash (Django admin)"
echo "  - https://console.cashflip.cash (React admin)"
echo ""
echo "Auto-renewal: Cron job runs daily at 3am"
