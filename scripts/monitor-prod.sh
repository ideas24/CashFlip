#!/bin/bash
# ============================================
# Cashflip Production Health Monitor
# Sends email alerts via Mailgun SMTP for:
# - VM/service down
# - Nginx down
# - SSL cert expiry
# - High CPU/memory
# - Disk space low
# ============================================

set -a
source /opt/cashflip/.env 2>/dev/null || true
set +a

ALERT_EMAIL="${ALERT_EMAIL:-contact@eddievolt.com}"
FROM_EMAIL="${FROM_EMAIL:-deploy@mail.eddievolt.com}"
SMTP_SERVER="${SMTP_SERVER:-smtp.mailgun.org}"
SMTP_PORT="${SMTP_PORT:-587}"
SMTP_USER="${SMTP_USER:-deploy@mail.eddievolt.com}"
SMTP_PASSWORD="${SMTP_PASSWORD}"
HOSTNAME=$(hostname)
LOG_FILE="/opt/cashflip/logs/monitor.log"
STATE_FILE="/tmp/cashflip_monitor_state"

mkdir -p /opt/cashflip/logs

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

send_alert() {
    local subject="$1"
    local body="$2"
    local state_key="$3"

    # Dedup: only send once per state key per hour
    if [ -n "$state_key" ] && [ -f "$STATE_FILE" ]; then
        last_sent=$(grep "^${state_key}=" "$STATE_FILE" 2>/dev/null | cut -d= -f2)
        now=$(date +%s)
        if [ -n "$last_sent" ] && [ $((now - last_sent)) -lt 3600 ]; then
            log "DEDUP: Skipping alert '$subject' (sent ${state_key} within 1hr)"
            return
        fi
    fi

    log "ALERT: $subject"

    if [ -z "$SMTP_PASSWORD" ]; then
        log "ERROR: SMTP_PASSWORD not set, cannot send email"
        return 1
    fi

    # Send via Mailgun SMTP using curl
    curl -s --url "smtp://${SMTP_SERVER}:${SMTP_PORT}" \
        --ssl-reqd \
        --mail-from "$FROM_EMAIL" \
        --mail-rcpt "$ALERT_EMAIL" \
        --user "${SMTP_USER}:${SMTP_PASSWORD}" \
        -T - <<EOF
From: Cashflip Monitor <${FROM_EMAIL}>
To: ${ALERT_EMAIL}
Subject: [CASHFLIP ALERT] ${subject}
Content-Type: text/plain; charset=utf-8

${body}

---
Server: ${HOSTNAME}
Time: $(date '+%Y-%m-%d %H:%M:%S UTC')
EOF

    if [ $? -eq 0 ]; then
        log "Email sent: $subject"
        # Record send time for dedup
        if [ -n "$state_key" ]; then
            touch "$STATE_FILE"
            grep -v "^${state_key}=" "$STATE_FILE" > "${STATE_FILE}.tmp" 2>/dev/null
            echo "${state_key}=$(date +%s)" >> "${STATE_FILE}.tmp"
            mv "${STATE_FILE}.tmp" "$STATE_FILE"
        fi
    else
        log "ERROR: Failed to send email: $subject"
    fi
}

# ==================== CHECKS ====================

check_gunicorn() {
    if ! systemctl is-active --quiet cashflip.service; then
        send_alert "Gunicorn DOWN on ${HOSTNAME}" \
            "cashflip.service is not running on ${HOSTNAME}.\n\nAttempting restart...\n\n$(systemctl status cashflip.service 2>&1 | head -20)" \
            "gunicorn_down"
        # Auto-restart
        systemctl restart cashflip.service
        sleep 5
        if systemctl is-active --quiet cashflip.service; then
            send_alert "Gunicorn RECOVERED on ${HOSTNAME}" \
                "cashflip.service was restarted successfully." \
                "gunicorn_recovered"
        fi
    fi
}

check_nginx() {
    if ! systemctl is-active --quiet nginx; then
        send_alert "Nginx DOWN on ${HOSTNAME}" \
            "nginx is not running on ${HOSTNAME}.\n\nAttempting restart...\n\n$(systemctl status nginx 2>&1 | head -20)" \
            "nginx_down"
        systemctl restart nginx
    fi
}

check_celery() {
    if systemctl list-unit-files | grep -q cashflip-celery; then
        if ! systemctl is-active --quiet cashflip-celery.service; then
            send_alert "Celery DOWN on ${HOSTNAME}" \
                "cashflip-celery.service is not running.\n\nAttempting restart...\n\n$(systemctl status cashflip-celery.service 2>&1 | head -20)" \
                "celery_down"
            systemctl restart cashflip-celery.service
        fi
    fi
}

check_disk() {
    local usage=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
    if [ "$usage" -gt 85 ]; then
        send_alert "Disk Space WARNING on ${HOSTNAME}: ${usage}%" \
            "Disk usage is at ${usage}% on ${HOSTNAME}.\n\n$(df -h /)\n\nLargest directories:\n$(du -sh /opt/cashflip/logs/* 2>/dev/null | sort -rh | head -10)" \
            "disk_warning"
    fi
    if [ "$usage" -gt 95 ]; then
        send_alert "Disk Space CRITICAL on ${HOSTNAME}: ${usage}%" \
            "CRITICAL: Disk is almost full at ${usage}%!\n\n$(df -h /)" \
            "disk_critical"
    fi
}

check_memory() {
    local mem_pct=$(free | awk '/Mem:/ {printf "%.0f", $3/$2*100}')
    if [ "$mem_pct" -gt 90 ]; then
        send_alert "Memory HIGH on ${HOSTNAME}: ${mem_pct}%" \
            "Memory usage is at ${mem_pct}% on ${HOSTNAME}.\n\n$(free -h)\n\nTop processes:\n$(ps aux --sort=-%mem | head -10)" \
            "memory_high"
    fi
}

check_cpu() {
    local cpu_load=$(cat /proc/loadavg | awk '{print $1}')
    local num_cpus=$(nproc)
    local threshold=$(echo "$num_cpus * 2" | bc)
    if (( $(echo "$cpu_load > $threshold" | bc -l) )); then
        send_alert "CPU Load HIGH on ${HOSTNAME}: ${cpu_load}" \
            "CPU load average is ${cpu_load} (threshold: ${threshold}, cores: ${num_cpus}).\n\nTop processes:\n$(ps aux --sort=-%cpu | head -10)" \
            "cpu_high"
    fi
}

check_health_endpoint() {
    local status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://127.0.0.1:8000/health/ 2>/dev/null)
    if [ "$status" != "200" ]; then
        send_alert "Health Check FAILED on ${HOSTNAME}: HTTP ${status}" \
            "The /health/ endpoint returned HTTP ${status} instead of 200.\n\nGunicorn status:\n$(systemctl status cashflip.service 2>&1 | head -15)" \
            "health_failed"
    fi
}

check_ssl_expiry() {
    local cert_file="/etc/letsencrypt/live/cashflip.amoano.com/fullchain.pem"
    if [ -f "$cert_file" ]; then
        local expiry_date=$(openssl x509 -enddate -noout -in "$cert_file" 2>/dev/null | cut -d= -f2)
        local expiry_epoch=$(date -d "$expiry_date" +%s 2>/dev/null)
        local now_epoch=$(date +%s)
        local days_left=$(( (expiry_epoch - now_epoch) / 86400 ))

        if [ "$days_left" -lt 7 ]; then
            send_alert "SSL Cert EXPIRING in ${days_left} days" \
                "SSL certificate for cashflip.amoano.com expires in ${days_left} days!\n\nExpiry: ${expiry_date}\n\nRun: certbot renew" \
                "ssl_expiry"
        fi
    fi
}

# ==================== MAIN ====================
check_gunicorn
check_nginx
check_celery
check_disk
check_memory
check_cpu
check_health_endpoint
check_ssl_expiry

log "Health check completed"
