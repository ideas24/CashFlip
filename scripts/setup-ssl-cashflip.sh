#!/bin/bash

# Setup SSL certificates for cashflip.cash domains
# Usage: ./scripts/setup-ssl-cashflip.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

err() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Azure VMSS details
RESOURCE_GROUP="cashflip-prod-rg"
APP_VMSS="cashflip-app-vmss"

# Function to run command on all VMSS instances
run_on_vmss() {
    local vmss_name="$1"
    local script="$2"
    local description="$3"
    
    log "Running on $vmss_name: $description"
    
    # Get all instance IDs
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
            err "Failed to run on $vmss_name instance $instance"
        }
        
        log "[$vmss_name] Instance $instance: Done"
    done
}

# SSL setup script
ssl_script='
echo "=== Setting up SSL for cashflip.cash domains ==="

# Request SSL certificate for new domains
sudo certbot certonly --webroot \
    -w /var/www/html \
    -d cashflip.cash \
    -d manage.cashflip.cash \
    -d console.cashflip.cash \
    --email admin@amoano.com \
    --non-interactive \
    --agree-tos \
    --expand \
    --renew-with-new-domains \
    --duplicate || echo "Certbot completed (may need DNS propagation first)"

echo "=== SSL setup complete ==="
echo "Note: If certbot failed, wait 5-10 minutes for DNS propagation and run again"
'

log "Setting up SSL certificates for cashflip.cash domains..."
run_on_vmss "$APP_VMSS" "$ssl_script" "Setup SSL for cashflip.cash"

log "SSL setup initiated on all App VMSS instances!"
echo ""
echo "The SSL certificates will be requested for:"
echo "  - cashflip.cash"
echo "  - manage.cashflip.cash"
echo "  - console.cashflip.cash"
echo ""
echo "If certbot failed due to DNS propagation, wait 5-10 minutes and run this script again."
