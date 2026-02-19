#!/bin/bash

# Update nginx config to serve React admin dashboard on console.cashflip.amoano.com
# Usage: ./scripts/update-nginx-admin.sh

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

# Nginx update script
nginx_script='
echo "=== Updating nginx config for React admin dashboard ==="

# Backup existing config
sudo cp /etc/nginx/sites-available/console.cashflip.amoano.com /etc/nginx/sites-available/console.cashflip.amoano.com.backup

# Create new config for React admin dashboard
sudo tee /etc/nginx/sites-available/console.cashflip.amoano.com > /dev/null << EOF
server {
    listen 80;
    server_name console.cashflip.amoano.com;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name console.cashflip.amoano.com;

    ssl_certificate /etc/letsencrypt/live/cashflip.amoano.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cashflip.amoano.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    client_max_body_size 20M;

    # Proxy to React admin dashboard (PM2 on port 3001)
    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for hot reload
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection upgrade;
    }

    # API endpoints proxy to Django
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Admin media and static files
    location /static/ {
        alias /opt/cashflip/app/staticfiles/;
        expires 30d;
        access_log off;
    }

    location /media/ {
        alias /opt/cashflip/app/media/;
        expires 7d;
        access_log off;
    }
}
EOF

# Test nginx configuration
sudo nginx -t

# Reload nginx if config is valid
if [ $? -eq 0 ]; then
    sudo systemctl reload nginx
    echo "Nginx configuration updated and reloaded successfully"
else
    echo "Nginx configuration test failed, restoring backup"
    sudo mv /etc/nginx/sites-available/console.cashflip.amoano.com.backup /etc/nginx/sites-available/console.cashflip.amoano.com
    sudo nginx -t
fi

echo "=== Nginx update complete ==="
'

log "Updating nginx configuration on App VMSS instances..."
run_on_vmss "$APP_VMSS" "$nginx_script" "Update nginx for React admin dashboard"

log "Nginx configuration updated on all App VMSS instances!"
echo ""
echo "The React admin dashboard should now be available at:"
echo "https://console.cashflip.amoano.com"
echo ""
echo "Django admin remains at:"
echo "https://manage.cashflip.amoano.com"
