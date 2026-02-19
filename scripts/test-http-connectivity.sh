#!/bin/bash

# Test HTTP connectivity on port 80
# Usage: ./scripts/test-http-connectivity.sh

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

# Test script
test_script='
echo "=== Testing HTTP connectivity ==="

# Create a simple test page
echo "CashFlip HTTP Test - $(hostname)" | sudo tee /var/www/html/test.html

# Test local HTTP
echo "Testing local HTTP on port 80..."
curl -s -I http://localhost/.well-known/acme-challenge/test || echo "Local HTTP failed"

# Check if nginx is listening on port 80
echo "Checking nginx listening ports..."
sudo netstat -tlnp | grep :80

echo "=== Test complete ==="
'

log "Testing HTTP connectivity on App VMSS instances..."
run_on_vmss "$APP_VMSS" "$test_script" "Test HTTP connectivity"

log "Connectivity test complete!"
