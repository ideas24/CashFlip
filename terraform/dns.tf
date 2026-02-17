# Porkbun DNS Automation for cashflip.amoano.com
# 
# After `terraform apply`, run this script to update DNS:
#
#   ./update_dns.sh $(terraform output -raw lb_public_ip)
#
# Requires PORKBUN_API_KEY and PORKBUN_SECRET_KEY environment variables
# (set in your .env or export them before running)

# DNS update script
resource "local_file" "dns_script" {
  filename = "${path.module}/update_dns.sh"
  content  = <<-SCRIPT
    #!/bin/bash
    # Update Porkbun DNS A records for cashflip production subdomains
    # Usage: ./update_dns.sh <LB_PUBLIC_IP>
    #
    # Requires env vars: PORKBUN_API_KEY, PORKBUN_SECRET_KEY
    # Source from .env:  source <(grep PORKBUN /path/to/.env)
    
    set -e
    
    LB_IP="$1"
    if [ -z "$LB_IP" ]; then
      echo "Usage: $0 <LB_PUBLIC_IP>"
      echo "  Requires: PORKBUN_API_KEY and PORKBUN_SECRET_KEY env vars"
      exit 1
    fi
    
    if [ -z "$PORKBUN_API_KEY" ] || [ -z "$PORKBUN_SECRET_KEY" ]; then
      echo "ERROR: PORKBUN_API_KEY and PORKBUN_SECRET_KEY must be set"
      echo "  export PORKBUN_API_KEY=pk1_..."
      echo "  export PORKBUN_SECRET_KEY=sk1_..."
      exit 1
    fi
    
    SUBDOMAINS=("cashflip" "manage.cashflip" "console.cashflip")
    
    echo "=== Updating DNS for cashflip production ==="
    echo "  Target IP: $LB_IP"
    echo ""
    
    for SUB in "$${SUBDOMAINS[@]}"; do
      echo "[$SUB.amoano.com] Deleting old A record..."
      curl -s -X POST "https://api.porkbun.com/api/json/v3/dns/deleteByNameType/amoano.com/A/$SUB" \
        -H "Content-Type: application/json" \
        -d "{\"apikey\":\"$PORKBUN_API_KEY\",\"secretapikey\":\"$PORKBUN_SECRET_KEY\"}" || true
      
      echo "[$SUB.amoano.com] Creating A -> $LB_IP"
      curl -s -X POST "https://api.porkbun.com/api/json/v3/dns/create/amoano.com" \
        -H "Content-Type: application/json" \
        -d "{\"apikey\":\"$PORKBUN_API_KEY\",\"secretapikey\":\"$PORKBUN_SECRET_KEY\",\"type\":\"A\",\"name\":\"$SUB\",\"content\":\"$LB_IP\",\"ttl\":\"300\"}"
      echo ""
    done
    
    echo "=== DNS updated. Allow 5 minutes for propagation. ==="
    for SUB in "$${SUBDOMAINS[@]}"; do
      echo "  $SUB.amoano.com -> $LB_IP"
    done
  SCRIPT

  file_permission = "0755"
}
