"""
Celery tasks for partner operations:
- Seamless wallet calls with exponential backoff retries
- Webhook delivery
- Settlement generation
"""

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=5)
def task_debit_operator(self, operator_id, operator_player_id, amount, currency_code, session_ref=''):
    """Debit operator wallet with exponential backoff retry."""
    from partner.models import Operator, OperatorPlayer
    from partner.wallet_service import call_operator_debit

    try:
        operator = Operator.objects.get(pk=operator_id)
        op_player = OperatorPlayer.objects.get(pk=operator_player_id)
    except (Operator.DoesNotExist, OperatorPlayer.DoesNotExist) as e:
        logger.error(f'task_debit_operator: {e}')
        return {'success': False, 'error': str(e)}

    tx = call_operator_debit(operator, op_player, amount, currency_code, session_ref)

    if tx.status == 'success':
        return {'success': True, 'tx_ref': tx.tx_ref, 'tx_id': str(tx.id)}

    # Retry with exponential backoff
    if self.request.retries < self.max_retries:
        delay = 5 * (2 ** self.request.retries)  # 5, 10, 20, 40, 80 seconds
        logger.warning(f'Retrying debit {tx.tx_ref} in {delay}s (attempt {self.request.retries + 1})')
        tx.retries = self.request.retries + 1
        tx.save(update_fields=['retries'])
        raise self.retry(countdown=delay)

    return {'success': False, 'tx_ref': tx.tx_ref, 'error': tx.error_message}


@shared_task(bind=True, max_retries=5, default_retry_delay=5)
def task_credit_operator(self, operator_id, operator_player_id, amount, currency_code, session_ref=''):
    """Credit operator wallet with exponential backoff retry."""
    from partner.models import Operator, OperatorPlayer
    from partner.wallet_service import call_operator_credit

    try:
        operator = Operator.objects.get(pk=operator_id)
        op_player = OperatorPlayer.objects.get(pk=operator_player_id)
    except (Operator.DoesNotExist, OperatorPlayer.DoesNotExist) as e:
        logger.error(f'task_credit_operator: {e}')
        return {'success': False, 'error': str(e)}

    tx = call_operator_credit(operator, op_player, amount, currency_code, session_ref)

    if tx.status == 'success':
        return {'success': True, 'tx_ref': tx.tx_ref, 'tx_id': str(tx.id)}

    if self.request.retries < self.max_retries:
        delay = 5 * (2 ** self.request.retries)
        logger.warning(f'Retrying credit {tx.tx_ref} in {delay}s (attempt {self.request.retries + 1})')
        tx.retries = self.request.retries + 1
        tx.save(update_fields=['retries'])
        raise self.retry(countdown=delay)

    return {'success': False, 'tx_ref': tx.tx_ref, 'error': tx.error_message}


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def task_rollback_operator(self, operator_id, operator_player_id, amount, currency_code, original_tx_ref):
    """Rollback a debit with retry."""
    from partner.models import Operator, OperatorPlayer
    from partner.wallet_service import call_operator_rollback

    try:
        operator = Operator.objects.get(pk=operator_id)
        op_player = OperatorPlayer.objects.get(pk=operator_player_id)
    except (Operator.DoesNotExist, OperatorPlayer.DoesNotExist) as e:
        logger.error(f'task_rollback_operator: {e}')
        return {'success': False, 'error': str(e)}

    tx = call_operator_rollback(operator, op_player, amount, currency_code, original_tx_ref)

    if tx.status == 'success':
        return {'success': True, 'tx_ref': tx.tx_ref}

    if self.request.retries < self.max_retries:
        delay = 10 * (2 ** self.request.retries)
        raise self.retry(countdown=delay)

    return {'success': False, 'tx_ref': tx.tx_ref, 'error': tx.error_message}


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def task_deliver_webhook(self, webhook_log_id):
    """Deliver a single webhook event to operator."""
    import hashlib
    import hmac as hmac_mod
    import json
    import requests
    from partner.models import OperatorWebhookLog, OperatorWebhookConfig

    try:
        log = OperatorWebhookLog.objects.select_related('operator').get(pk=webhook_log_id)
    except OperatorWebhookLog.DoesNotExist:
        return {'success': False, 'error': 'Log not found'}

    try:
        config = OperatorWebhookConfig.objects.get(operator=log.operator, is_active=True)
    except OperatorWebhookConfig.DoesNotExist:
        log.status = 'failed'
        log.error_message = 'No active webhook config'
        log.save(update_fields=['status'])
        return {'success': False, 'error': 'No webhook config'}

    # Sign payload with operator's first active API key secret
    api_key = log.operator.api_keys.filter(is_active=True).first()
    body = json.dumps(log.payload, default=str).encode('utf-8')
    signature = ''
    if api_key:
        signature = hmac_mod.new(
            api_key.api_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()

    log.signature = signature
    log.save(update_fields=['signature'])

    headers = {
        'Content-Type': 'application/json',
        'X-Cashflip-Signature': signature,
        'X-Cashflip-Event': log.event,
    }

    try:
        resp = requests.post(config.webhook_url, data=body, headers=headers, timeout=15)
        log.response_status_code = resp.status_code
        log.response_body = resp.text[:2000]

        if resp.status_code in (200, 201, 202, 204):
            log.status = 'delivered'
            log.delivered_at = timezone.now()
            log.save(update_fields=['status', 'response_status_code', 'response_body', 'delivered_at'])
            return {'success': True}

        log.retries += 1
        log.save(update_fields=['response_status_code', 'response_body', 'retries'])

        if self.request.retries < self.max_retries:
            delay = 30 * (2 ** self.request.retries)  # 30, 60, 120 seconds
            raise self.retry(countdown=delay)

        log.status = 'failed'
        log.save(update_fields=['status'])
        return {'success': False, 'error': f'HTTP {resp.status_code}'}

    except requests.RequestException as e:
        log.retries += 1
        log.save(update_fields=['retries'])

        if self.request.retries < self.max_retries:
            delay = 30 * (2 ** self.request.retries)
            raise self.retry(countdown=delay)

        log.status = 'failed'
        log.response_body = str(e)[:2000]
        log.save(update_fields=['status', 'response_body'])
        return {'success': False, 'error': str(e)}


@shared_task
def task_generate_settlements():
    """
    Generate settlement records for all active operators.
    Run daily via Celery Beat.
    """
    from datetime import date, timedelta
    from decimal import Decimal
    from django.db.models import Sum, Count
    from partner.models import Operator, OperatorSession, OperatorSettlement

    today = date.today()
    yesterday = today - timedelta(days=1)

    for operator in Operator.objects.filter(status='active'):
        # Check if settlement already exists for this period
        if operator.settlement_frequency == 'daily':
            period_start = yesterday
            period_end = yesterday
        elif operator.settlement_frequency == 'weekly':
            period_start = yesterday - timedelta(days=6)
            period_end = yesterday
            # Only generate on Mondays for weekly
            if today.weekday() != 0:
                continue
        else:  # monthly
            if today.day != 1:
                continue
            period_end = yesterday
            period_start = period_end.replace(day=1)

        if OperatorSettlement.objects.filter(
            operator=operator, period_start=period_start, period_end=period_end
        ).exists():
            continue

        # Aggregate session data
        sessions = OperatorSession.objects.filter(
            operator=operator,
            game_session__created_at__date__gte=period_start,
            game_session__created_at__date__lte=period_end,
        )

        agg = sessions.aggregate(
            total_bets=Sum('game_session__stake_amount'),
            total_wins=Sum('game_session__cashout_balance'),
            total_sessions=Count('id'),
        )

        total_bets = agg['total_bets'] or Decimal('0')
        total_wins = agg['total_wins'] or Decimal('0')
        total_sessions = agg['total_sessions'] or 0
        ggr = total_bets - total_wins

        if ggr <= 0 and total_sessions == 0:
            continue  # Nothing to settle

        commission_pct = operator.commission_percent
        commission_amount = (ggr * commission_pct / Decimal('100')).quantize(Decimal('0.01'))
        net_operator = (ggr - commission_amount).quantize(Decimal('0.01'))

        OperatorSettlement.objects.create(
            operator=operator,
            period_start=period_start,
            period_end=period_end,
            total_bets=total_bets,
            total_wins=total_wins,
            total_sessions=total_sessions,
            ggr=ggr,
            commission_percent=commission_pct,
            commission_amount=commission_amount,
            net_operator_amount=net_operator,
            currency_code='GHS',
        )
        logger.info(
            f'Settlement created for {operator.name}: '
            f'{period_start} to {period_end}, GGR={ggr}, commission={commission_amount}'
        )
