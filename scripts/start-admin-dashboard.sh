#!/bin/bash

# Start the admin dashboard with PM2 on production VMs
# Usage: ./scripts/start-admin-dashboard.sh

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

# Start script
start_script='
echo "=== Starting Admin Dashboard with PM2 ==="

cd /opt/cashflip/app/admin-dashboard

# Check if ecosystem.config.js exists
if [ ! -f "ecosystem.config.js" ]; then
    echo "Creating PM2 ecosystem config..."
    cat > ecosystem.config.js << EOF
module.exports = {
  apps: [{
    name: "cashflip-admin",
    script: "npm",
    args: "start",
    cwd: "/opt/cashflip/app/admin-dashboard",
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: "1G",
    env: {
      NODE_ENV: "production",
      PORT: 3001
    }
  }]
};
EOF
fi

# Start the app with PM2
pm2 start ecosystem.config.js

# Save PM2 configuration
pm2 save

# Setup PM2 startup script
pm2 startup | tail -1 | bash

echo "=== Admin Dashboard started ==="
echo "Process list:"
pm2 list
'

log "Starting admin dashboard on App VMSS instances..."
run_on_vmss "$APP_VMSS" "$start_script" "Start admin dashboard with PM2"

log "Admin dashboard started on all App VMSS instances!"
echo ""
echo "Admin dashboard should now be running at:"
echo "https://manage.cashflip.amoano.com"
echo ""
echo "To check status: SSH into VM and run: pm2 list"
