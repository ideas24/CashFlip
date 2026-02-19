#!/bin/bash

# Install Node.js, npm, and pm2 on production VMs
# Usage: ./scripts/install-nodejs.sh

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

# Installation script
install_script='
echo "=== Installing Node.js, npm, and pm2 ==="

# Update package list
sudo apt-get update

# Install Node.js 18.x (LTS)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify installation
echo "Node.js version: $(node --version)"
echo "npm version: $(npm --version)"

# Install pm2 globally
sudo npm install -g pm2

# Verify pm2
echo "pm2 version: $(pm2 --version)"

# Create pm2 config directory if it does not exist
mkdir -p ~/.pm2

echo "=== Installation complete ==="
'

log "Starting Node.js/npm/pm2 installation on App VMSS instances..."
run_on_vmss "$APP_VMSS" "$install_script" "Install Node.js, npm, and pm2"

log "Installation complete on all App VMSS instances!"
echo ""
echo "Next steps:"
echo "1. Run: ./scripts/deploy-prod.sh --admin"
echo "2. Verify admin dashboard at: https://manage.cashflip.amoano.com"
