"""
Webhook dispatch helper — creates log entries and queues Celery delivery tasks.
"""

import logging
from partner.models import OperatorWebhookConfig, OperatorWebhookLog

logger = logging.getLogger(__name__)


def dispatch_webhook(operator, event, payload):
    """
    Dispatch a webhook event to an operator (if subscribed).
    Creates a WebhookLog entry and queues the delivery task.
    """
    try:
        config = OperatorWebhookConfig.objects.get(operator=operator, is_active=True)
    except OperatorWebhookConfig.DoesNotExist:
        return  # No webhook configured — silently skip

    # Check if operator is subscribed to this event
    if config.subscribed_events and event not in config.subscribed_events:
        return

    log = OperatorWebhookLog.objects.create(
        operator=operator,
        event=event,
        payload=payload,
    )

    # Queue async delivery
    from partner.tasks import task_deliver_webhook
    task_deliver_webhook.delay(str(log.id))

    logger.info(f'Webhook queued: {event} → {operator.name}')
