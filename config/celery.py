"""
Cashflip Celery Configuration
Modeled after ReachMint's robust celery setup with queue routing,
beat scheduling, and proper task isolation.
"""

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('cashflip')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Queue definitions
app.conf.task_default_queue = 'default'

app.conf.task_routes = {
    'partner.*': {'queue': 'default'},
    'payments.*': {'queue': 'game'},
    'game.*': {'queue': 'game'},
    'analytics.*': {'queue': 'default'},
    'ads.*': {'queue': 'default'},
    'referrals.*': {'queue': 'default'},
}

app.conf.task_queues = {
    'default': {
        'exchange': 'default',
        'routing_key': 'default',
    },
    'game': {
        'exchange': 'game',
        'routing_key': 'game',
    },
}

app.autodiscover_tasks()

# Celery Beat Schedule
from celery.schedules import crontab

app.conf.beat_schedule = {
    # Generate operator settlements daily at 3 AM
    'generate-operator-settlements': {
        'task': 'partner.tasks.task_generate_settlements',
        'schedule': crontab(hour=3, minute=0),
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
