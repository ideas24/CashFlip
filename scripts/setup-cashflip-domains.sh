#!/bin/bash

# Setup nginx configurations for cashflip.cash domains
# Usage: ./scripts/setup-cashflip-domains.sh

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

# Nginx configuration script
nginx_script='
echo "=== Setting up nginx configs for cashflip.cash domains ==="

# Main domain config (cashflip.cash -> Django app)
sudo tee /etc/nginx/sites-available/cashflip.cash > /dev/null << "EOF"
server {
    listen 80;
    server_name cashflip.cash;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name cashflip.cash;

    ssl_certificate /etc/letsencrypt/live/cashflip.amoano.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cashflip.amoano.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    client_max_body_size 20M;

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

    location /health/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        access_log off;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Django admin config (manage.cashflip.cash -> Django admin)
sudo tee /etc/nginx/sites-available/manage.cashflip.cash > /dev/null << "EOF"
server {
    listen 80;
    server_name manage.cashflip.cash;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name manage.cashflip.cash;

    ssl_certificate /etc/letsencrypt/live/cashflip.amoano.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cashflip.amoano.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    client_max_body_size 20M;

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

    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        access_log off;
    }

    location / {
        return 302 /admin/;
    }
}
EOF

# React admin config (console.cashflip.cash -> React admin dashboard)
sudo tee /etc/nginx/sites-available/console.cashflip.cash > /dev/null << "EOF"
server {
    listen 80;
    server_name console.cashflip.cash;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name console.cashflip.cash;

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

# Enable the new sites
sudo ln -sf /etc/nginx/sites-available/cashflip.cash /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/manage.cashflip.cash /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/console.cashflip.cash /etc/nginx/sites-enabled/

# Test nginx configuration
sudo nginx -t

# Reload nginx if config is valid
if [ $? -eq 0 ]; then
    sudo systemctl reload nginx
    echo "Nginx configurations added and reloaded successfully"
else
    echo "Nginx configuration test failed"
    exit 1
fi

echo "=== Nginx setup complete ==="
echo "Added sites:"
echo "  - cashflip.cash (main Django app)"
echo "  - manage.cashflip.cash (Django admin)"
echo "  - console.cashflip.cash (React admin dashboard)"
'

log "Setting up nginx configurations for cashflip.cash domains..."
run_on_vmss "$APP_VMSS" "$nginx_script" "Setup nginx for cashflip.cash domains"

log "Nginx configurations setup complete!"
echo ""
echo "Next steps:"
echo "1. Get the load balancer IP: az network lb show -g cashflip-prod-rg -n cashflip-lb --query \"frontendIPConfigurations[0].privateIPAddress\" -o tsv"
echo "2. Update DNS: ./terraform/update_dns_cashflip.sh <LB_IP>"
echo "3. Deploy with new env: ./scripts/deploy-prod.sh --with-env terraform/production.env"
