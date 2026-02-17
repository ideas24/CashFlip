"""
Seamless wallet service — calls operator's debit/credit/rollback endpoints.

All calls are synchronous helpers used by Celery tasks for retry logic.
The operator configures their URLs in the admin portal.
"""

import uuid
import logging

import requests
from django.utils import timezone

from partner.models import Operator, OperatorPlayer, OperatorTransaction

logger = logging.getLogger(__name__)

WALLET_CALL_TIMEOUT = 15  # seconds


def _build_headers(operator):
    """Build headers for calling operator wallet endpoints."""
    headers = {'Content-Type': 'application/json'}
    if operator.wallet_auth_token:
        headers['Authorization'] = f'Bearer {operator.wallet_auth_token}'
    return headers


def call_operator_debit(operator, operator_player, amount, currency_code, session_ref=''):
    """
    Call operator's debit_url to debit player balance for a bet.

    Returns:
        OperatorTransaction with status 'success' or 'failed'
    """
    tx_ref = f'CF-DEB-{uuid.uuid4().hex[:16].upper()}'

    tx = OperatorTransaction.objects.create(
        operator=operator,
        operator_player=operator_player,
        tx_type='debit',
        tx_ref=tx_ref,
        amount=amount,
        currency_code=currency_code,
    )

    if not operator.debit_url:
        tx.status = 'failed'
        tx.error_message = 'Operator debit_url not configured'
        tx.completed_at = timezone.now()
        tx.save(update_fields=['status', 'error_message', 'completed_at'])
        logger.error(f'Debit failed: no debit_url for {operator.name}')
        return tx

    payload = {
        'player_id': operator_player.ext_player_id,
        'amount': str(amount),
        'currency': currency_code,
        'tx_ref': tx_ref,
        'type': 'bet',
        'session_ref': session_ref,
    }
    tx.request_payload = payload
    tx.save(update_fields=['request_payload'])

    try:
        resp = requests.post(
            operator.debit_url,
            json=payload,
            headers=_build_headers(operator),
            timeout=WALLET_CALL_TIMEOUT,
        )
        tx.response_payload = _safe_json(resp)

        if resp.status_code in (200, 201):
            resp_data = resp.json()
            if resp_data.get('success', False):
                tx.status = 'success'
                tx.completed_at = timezone.now()
                tx.save(update_fields=['status', 'response_payload', 'completed_at'])
                logger.info(f'Debit success: {tx_ref} {amount} {currency_code} for {operator.name}')
                return tx

        tx.status = 'failed'
        tx.error_message = f'HTTP {resp.status_code}: {resp.text[:500]}'
        tx.completed_at = timezone.now()
        tx.save(update_fields=['status', 'response_payload', 'error_message', 'completed_at'])
        logger.error(f'Debit failed: {tx_ref} - {tx.error_message}')
        return tx

    except requests.RequestException as e:
        tx.status = 'failed'
        tx.error_message = str(e)[:500]
        tx.completed_at = timezone.now()
        tx.save(update_fields=['status', 'error_message', 'completed_at'])
        logger.error(f'Debit exception: {tx_ref} - {e}')
        return tx


def call_operator_credit(operator, operator_player, amount, currency_code, session_ref=''):
    """
    Call operator's credit_url to credit player balance for a win/cashout.

    Returns:
        OperatorTransaction with status 'success' or 'failed'
    """
    tx_ref = f'CF-CRD-{uuid.uuid4().hex[:16].upper()}'

    tx = OperatorTransaction.objects.create(
        operator=operator,
        operator_player=operator_player,
        tx_type='credit',
        tx_ref=tx_ref,
        amount=amount,
        currency_code=currency_code,
    )

    if not operator.credit_url:
        tx.status = 'failed'
        tx.error_message = 'Operator credit_url not configured'
        tx.completed_at = timezone.now()
        tx.save(update_fields=['status', 'error_message', 'completed_at'])
        logger.error(f'Credit failed: no credit_url for {operator.name}')
        return tx

    payload = {
        'player_id': operator_player.ext_player_id,
        'amount': str(amount),
        'currency': currency_code,
        'tx_ref': tx_ref,
        'type': 'win',
        'session_ref': session_ref,
    }
    tx.request_payload = payload
    tx.save(update_fields=['request_payload'])

    try:
        resp = requests.post(
            operator.credit_url,
            json=payload,
            headers=_build_headers(operator),
            timeout=WALLET_CALL_TIMEOUT,
        )
        tx.response_payload = _safe_json(resp)

        if resp.status_code in (200, 201):
            resp_data = resp.json()
            if resp_data.get('success', False):
                tx.status = 'success'
                tx.completed_at = timezone.now()
                tx.save(update_fields=['status', 'response_payload', 'completed_at'])
                logger.info(f'Credit success: {tx_ref} {amount} {currency_code} for {operator.name}')
                return tx

        tx.status = 'failed'
        tx.error_message = f'HTTP {resp.status_code}: {resp.text[:500]}'
        tx.completed_at = timezone.now()
        tx.save(update_fields=['status', 'response_payload', 'error_message', 'completed_at'])
        logger.error(f'Credit failed: {tx_ref} - {tx.error_message}')
        return tx

    except requests.RequestException as e:
        tx.status = 'failed'
        tx.error_message = str(e)[:500]
        tx.completed_at = timezone.now()
        tx.save(update_fields=['status', 'error_message', 'completed_at'])
        logger.error(f'Credit exception: {tx_ref} - {e}')
        return tx


def call_operator_rollback(operator, operator_player, amount, currency_code, original_tx_ref):
    """
    Call operator's rollback_url to reverse a debit that can't be fulfilled.

    Returns:
        OperatorTransaction with status 'success' or 'failed'
    """
    tx_ref = f'CF-RBK-{uuid.uuid4().hex[:16].upper()}'

    tx = OperatorTransaction.objects.create(
        operator=operator,
        operator_player=operator_player,
        tx_type='rollback',
        tx_ref=tx_ref,
        amount=amount,
        currency_code=currency_code,
    )

    if not operator.rollback_url:
        tx.status = 'failed'
        tx.error_message = 'Operator rollback_url not configured'
        tx.completed_at = timezone.now()
        tx.save(update_fields=['status', 'error_message', 'completed_at'])
        logger.error(f'Rollback failed: no rollback_url for {operator.name}')
        return tx

    payload = {
        'player_id': operator_player.ext_player_id,
        'amount': str(amount),
        'currency': currency_code,
        'tx_ref': tx_ref,
        'original_tx_ref': original_tx_ref,
        'type': 'rollback',
    }
    tx.request_payload = payload
    tx.save(update_fields=['request_payload'])

    try:
        resp = requests.post(
            operator.rollback_url,
            json=payload,
            headers=_build_headers(operator),
            timeout=WALLET_CALL_TIMEOUT,
        )
        tx.response_payload = _safe_json(resp)

        if resp.status_code in (200, 201):
            tx.status = 'success'
            tx.completed_at = timezone.now()
            tx.save(update_fields=['status', 'response_payload', 'completed_at'])
            logger.info(f'Rollback success: {tx_ref} for original {original_tx_ref}')
            return tx

        tx.status = 'failed'
        tx.error_message = f'HTTP {resp.status_code}: {resp.text[:500]}'
        tx.completed_at = timezone.now()
        tx.save(update_fields=['status', 'response_payload', 'error_message', 'completed_at'])
        logger.error(f'Rollback failed: {tx_ref} - {tx.error_message}')
        return tx

    except requests.RequestException as e:
        tx.status = 'failed'
        tx.error_message = str(e)[:500]
        tx.completed_at = timezone.now()
        tx.save(update_fields=['status', 'error_message', 'completed_at'])
        logger.error(f'Rollback exception: {tx_ref} - {e}')
        return tx


def _safe_json(response):
    """Safely extract JSON from response."""
    try:
        return response.json()
    except Exception:
        return {'raw': response.text[:1000]}
