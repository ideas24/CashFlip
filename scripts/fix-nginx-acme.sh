#!/bin/bash

# Fix nginx configurations to properly handle ACME challenges
# Usage: ./scripts/fix-nginx-acme.sh

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

# Nginx fix script
nginx_script='
echo "=== Fixing nginx for ACME challenges ==="

# Create a default catch-all config for port 80 to handle ACME challenges
sudo tee /etc/nginx/sites-available/default-http > /dev/null << "EOF"
server {
    listen 80 default_server;
    server_name _;
    
    # Handle ACME challenges for all domains
    location /.well-known/acme-challenge/ {
        root /var/www/html;
        try_files $uri =404;
    }
    
    # Redirect all other HTTP traffic to HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}
EOF

# Enable the default HTTP config
sudo ln -sf /etc/nginx/sites-available/default-http /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
sudo nginx -t

# Reload nginx if config is valid
if [ $? -eq 0 ]; then
    sudo systemctl reload nginx
    echo "Nginx configuration fixed and reloaded successfully"
else
    echo "Nginx configuration test failed"
    exit 1
fi

echo "=== Nginx fix complete ==="
'

log "Fixing nginx configurations for ACME challenges..."
run_on_vmss "$APP_VMSS" "$nginx_script" "Fix nginx for ACME"

log "Nginx configurations fixed!"
echo ""
echo "Now retrying SSL certificate setup..."
