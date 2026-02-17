# Cashflip Staging - Nginx Configuration
# Rate limiting zones
limit_req_zone $binary_remote_addr zone=cashflip_general:10m rate=30r/s;
limit_req_zone $binary_remote_addr zone=cashflip_api:10m rate=20r/s;
limit_req_zone $binary_remote_addr zone=cashflip_auth:10m rate=5r/m;
limit_conn_zone $binary_remote_addr zone=cashflip_conn:10m;

# HTTP -> HTTPS redirect
server {
    listen 80;
    server_name demo.cashflip.amoano.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name demo.cashflip.amoano.com;

    # SSL (managed by Certbot)
    # ssl_certificate /etc/letsencrypt/live/demo.cashflip.amoano.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/demo.cashflip.amoano.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com https://apis.google.com https://connect.facebook.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://api.paystack.co https://graph.facebook.com; frame-src https://checkout.paystack.com https://accounts.google.com https://www.facebook.com;" always;

    # Connection limits
    limit_conn cashflip_conn 50;

    # Client limits
    client_max_body_size 10M;
    client_body_timeout 30s;
    client_header_timeout 30s;

    # Static files
    location /static/ {
        alias /home/terminal_ideas/cashflip/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Media files
    location /media/ {
        alias /home/terminal_ideas/cashflip/media/;
        expires 7d;
        add_header Cache-Control "public";
        access_log off;
    }

    # Auth API (strict rate limiting)
    location /api/accounts/auth/ {
        limit_req zone=cashflip_auth burst=3 nodelay;
        proxy_pass http://unix:/home/terminal_ideas/cashflip/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Webhooks (no rate limiting - payment providers)
    location /api/payments/webhooks/ {
        proxy_pass http://unix:/home/terminal_ideas/cashflip/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API endpoints
    location /api/ {
        limit_req zone=cashflip_api burst=20 nodelay;
        proxy_pass http://unix:/home/terminal_ideas/cashflip/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Admin
    location /admin/ {
        limit_req zone=cashflip_general burst=10 nodelay;
        proxy_pass http://unix:/home/terminal_ideas/cashflip/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check
    location /health/ {
        proxy_pass http://unix:/home/terminal_ideas/cashflip/gunicorn.sock;
        proxy_set_header Host $host;
        access_log off;
    }

    # Social auth
    location /auth/ {
        proxy_pass http://unix:/home/terminal_ideas/cashflip/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Main app (SPA)
    location / {
        limit_req zone=cashflip_general burst=30 nodelay;
        proxy_pass http://unix:/home/terminal_ideas/cashflip/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
