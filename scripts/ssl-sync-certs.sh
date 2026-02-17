#!/bin/bash
# ============================================
# SSL Certificate Sync for Cashflip Production
# Run as certbot renewal hook on VM0 to copy
# certs to all other app VMs via Azure CLI.
# ============================================

set -e

RESOURCE_GROUP="cashflip-prod-rg"
VMSS_NAME="cashflip-app-vmss"
CERT_DIR="/etc/letsencrypt/live/cashflip.amoano.com"
LOG_FILE="/opt/cashflip/logs/ssl-sync.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE" 2>/dev/null
    echo "$1"
}

# Read cert files
FULLCHAIN=$(cat "${CERT_DIR}/fullchain.pem" | base64 -w0)
PRIVKEY=$(cat "${CERT_DIR}/privkey.pem" | base64 -w0)

# Get all VM instance IDs
INSTANCES=$(az vmss list-instances --resource-group "$RESOURCE_GROUP" --name "$VMSS_NAME" --query "[].instanceId" -o tsv 2>/dev/null)

CURRENT_HOSTNAME=$(hostname)

for INSTANCE_ID in $INSTANCES; do
    # Get this instance's hostname to skip self
    INST_NAME=$(az vmss list-instances --resource-group "$RESOURCE_GROUP" --name "$VMSS_NAME" --query "[?instanceId=='${INSTANCE_ID}'].osProfile.computerName" -o tsv 2>/dev/null)

    if [ "$INST_NAME" = "$CURRENT_HOSTNAME" ]; then
        log "Skipping self (instance ${INSTANCE_ID})"
        continue
    fi

    log "Syncing certs to instance ${INSTANCE_ID} (${INST_NAME})..."

    az vmss run-command invoke \
        --resource-group "$RESOURCE_GROUP" \
        --name "$VMSS_NAME" \
        --instance-id "$INSTANCE_ID" \
        --command-id RunShellScript \
        --scripts "
#!/bin/bash
mkdir -p /etc/letsencrypt/live/cashflip.amoano.com
echo '${FULLCHAIN}' | base64 -d > /etc/letsencrypt/live/cashflip.amoano.com/fullchain.pem
echo '${PRIVKEY}' | base64 -d > /etc/letsencrypt/live/cashflip.amoano.com/privkey.pem
chmod 600 /etc/letsencrypt/live/cashflip.amoano.com/privkey.pem
nginx -t && systemctl reload nginx
echo 'Certs synced and nginx reloaded'
" --output json 2>&1 | jq -r '.value[0].message' >> "$LOG_FILE" 2>/dev/null

    if [ $? -eq 0 ]; then
        log "Success: instance ${INSTANCE_ID}"
    else
        log "FAILED: instance ${INSTANCE_ID}"
    fi
done

log "SSL cert sync complete"
