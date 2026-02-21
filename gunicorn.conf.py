import multiprocessing
import os
from pathlib import Path

# Auto-detect base directory (works on dev + production VMs)
_BASE_DIR = Path(__file__).resolve().parent
_LOG_DIR = _BASE_DIR / 'logs'
_LOG_DIR.mkdir(exist_ok=True)

# Server socket
bind = os.getenv('GUNICORN_BIND', f'unix:{_BASE_DIR / "gunicorn.sock"}')
backlog = 2048

# Worker processes
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
worker_connections = 1000
timeout = 60
keepalive = 2

# Restart workers after this many requests (prevents memory leaks)
max_requests = 1000
max_requests_jitter = 50

# Logging
errorlog = str(_LOG_DIR / 'gunicorn_error.log')
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')
accesslog = str(_LOG_DIR / 'gunicorn_access.log')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "cashflip"

# Server mechanics
daemon = False
pidfile = str(_BASE_DIR / 'gunicorn.pid')
tmp_upload_dir = None

# SSL (handled by Nginx/Certbot)
keyfile = None
certfile = None
