#!/bin/bash
# Update Porkbun DNS A records for cashflip.cash domain
# Usage: ./update_dns_cashflip.sh <LB_PUBLIC_IP>
#
# Requires env vars: PORKBUN_API_KEY, PORKBUN_SECRET_KEY
    
set -e
    
LB_IP="$1"
if [ -z "$LB_IP" ]; then
  echo "Usage: $0 <LB_PUBLIC_IP>"
  echo "  Requires: PORKBUN_API_KEY and PORKBUN_SECRET_KEY env vars"
  exit 1
fi
    
if [ -z "$PORKBUN_API_KEY" ] || [ -z "$PORKBUN_SECRET_KEY" ]; then
  echo "ERROR: PORKBUN_API_KEY and PORKBUN_SECRET_KEY must be set"
  echo "  Source from production.env: source terraform/production.env"
  exit 1
fi
    
SUBDOMAINS=("cashflip" "manage.cashflip" "console.cashflip")
    
echo "=== Updating DNS for cashflip.cash domain ==="
echo "  Target IP: $LB_IP"
echo ""
    
for SUB in "${SUBDOMAINS[@]}"; do
  echo "[$SUB.cashflip.cash] Deleting old A record..."
  curl -s -X POST "https://api.porkbun.com/api/json/v3/dns/deleteByNameType/cashflip.cash/A/$SUB" \
    -H "Content-Type: application/json" \
    -d "{\"apikey\":\"$PORKBUN_API_KEY\",\"secretapikey\":\"$PORKBUN_SECRET_KEY\"}" || true
      
  echo "[$SUB.cashflip.cash] Creating A -> $LB_IP"
  curl -s -X POST "https://api.porkbun.com/api/json/v3/dns/create/cashflip.cash" \
    -H "Content-Type: application/json" \
    -d "{\"apikey\":\"$PORKBUN_API_KEY\",\"secretapikey\":\"$PORKBUN_SECRET_KEY\",\"type\":\"A\",\"name\":\"$SUB\",\"content\":\"$LB_IP\",\"ttl\":\"300\"}"
  echo ""
done
    
echo "=== DNS updated. Allow 5 minutes for propagation. ==="
for SUB in "${SUBDOMAINS[@]}"; do
  echo "  $SUB.cashflip.cash -> $LB_IP"
done
