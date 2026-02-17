import multiprocessing

# Server socket
bind = "unix:/home/terminal_ideas/cashflip/gunicorn.sock"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 60
keepalive = 2

# Restart workers after this many requests
max_requests = 1000
max_requests_jitter = 50

# Logging
errorlog = "/home/terminal_ideas/cashflip/logs/gunicorn_error.log"
loglevel = "info"
accesslog = "/home/terminal_ideas/cashflip/logs/gunicorn_access.log"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "cashflip"

# Server mechanics
daemon = False
pidfile = "/home/terminal_ideas/cashflip/gunicorn.pid"
user = "terminal_ideas"
group = "terminal_ideas"
tmp_upload_dir = None

# SSL (handled by Nginx/Certbot)
keyfile = None
certfile = None
