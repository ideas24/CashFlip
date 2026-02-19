#!/bin/bash

# Fix ACME webroot directory
# Usage: ./scripts/fix-acme-webroot.sh

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

# Fix webroot script
fix_script='
echo "=== Fixing ACME webroot ==="

# Create ACME challenge directory
sudo mkdir -p /var/www/html/.well-known/acme-challenge
sudo chown -R www-data:www-data /var/www/html/.well-known
sudo chmod -R 755 /var/www/html/.well-known

# Create a test file
echo "ACME Challenge Test - $(hostname)" | sudo tee /var/www/html/.well-known/acme-challenge/test

# Test the ACME challenge path
echo "Testing ACME challenge path..."
curl -s http://localhost/.well-known/acme-challenge/test || echo "ACME challenge test failed"

# Check permissions
echo "Checking directory permissions:"
ls -la /var/www/html/.well-known/

echo "=== ACME webroot fix complete ==="
'

log "Fixing ACME webroot on App VMSS instances..."
run_on_vmss "$APP_VMSS" "$fix_script" "Fix ACME webroot"

log "ACME webroot fix complete!"
