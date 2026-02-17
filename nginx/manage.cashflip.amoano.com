# Cashflip Admin Panel - Nginx Configuration
# Only serves /admin/ and /static/ - no game routes

server {
    listen 80;
    server_name manage.cashflip.amoano.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name manage.cashflip.amoano.com;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Tight client limits
    client_max_body_size 20M;
    client_body_timeout 30s;
    client_header_timeout 30s;

    # Static files (admin CSS/JS)
    location /static/ {
        alias /home/terminal_ideas/cashflip/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Media files (banknote uploads etc)
    location /media/ {
        alias /home/terminal_ideas/cashflip/media/;
        expires 7d;
        add_header Cache-Control "public";
        access_log off;
    }

    # Admin panel
    location /admin/ {
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

    # Everything else redirects to admin login
    location / {
        return 302 /admin/;
    }
}
