# Porkbun DNS Automation for cashflip.amoano.com
# 
# After `terraform apply`, run this script to update DNS:
#
#   ./update_dns.sh $(terraform output -raw lb_public_ip)
#
# The script uses Porkbun API to point cashflip.amoano.com -> LB IP

# DNS update script
resource "local_file" "dns_script" {
  filename = "${path.module}/update_dns.sh"
  content  = <<-SCRIPT
    #!/bin/bash
    # Update Porkbun DNS A record for cashflip.amoano.com
    # Usage: ./update_dns.sh <LB_PUBLIC_IP>
    
    set -e
    
    LB_IP="$1"
    if [ -z "$LB_IP" ]; then
      echo "Usage: $0 <LB_PUBLIC_IP>"
      exit 1
    fi
    
    API_KEY="pk1_ec05cee783e1a5c039879a5ccd682590cf96310f0a2ea73c0c1c0fe07687e802"
    SECRET_KEY="sk1_fe2256e4a8bf539ea5f1bbf59cfeca909c7c5b51e48199538d98285fa386c441"
    
    echo "Setting cashflip.amoano.com -> $LB_IP"
    
    # Delete existing A record
    curl -s -X POST "https://api.porkbun.com/api/json/v3/dns/deleteByNameType/amoano.com/A/cashflip" \
      -H "Content-Type: application/json" \
      -d "{\"apikey\":\"$API_KEY\",\"secretapikey\":\"$SECRET_KEY\"}"
    
    echo ""
    
    # Create new A record
    RESULT=$(curl -s -X POST "https://api.porkbun.com/api/json/v3/dns/create/amoano.com" \
      -H "Content-Type: application/json" \
      -d "{\"apikey\":\"$API_KEY\",\"secretapikey\":\"$SECRET_KEY\",\"type\":\"A\",\"name\":\"cashflip\",\"content\":\"$LB_IP\",\"ttl\":\"300\"}")
    
    echo "$RESULT"
    echo ""
    echo "DNS updated. Allow 5 minutes for propagation."
  SCRIPT

  file_permission = "0755"
}
