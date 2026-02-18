"""
Cashflip Payment Services
Adapters for Orchard (Mobile Money) and Paystack (Card) - reusing reachmint patterns.
"""

import uuid
import json
import hmac
import hashlib
import time
import logging
import requests
import re
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ==================== Mobile Money Utilities ====================

def validate_mobile_number(number):
    """Validate Ghanaian mobile money numbers."""
    cleaned = re.sub(r'\D', '', number)
    pattern = r'^0(23|24|20|27|26|28|54|55|56|57|59)\d{7}$'
    return re.match(pattern, cleaned) is not None


def detect_network(number):
    """Detect mobile money network from phone number."""
    cleaned = re.sub(r'\D', '', number)
    if cleaned.startswith('233'):
        cleaned = cleaned[3:]
    if cleaned.startswith('0'):
        cleaned = cleaned[1:]
    prefix_map = {
        '23': 'MTN', '24': 'MTN', '54': 'MTN', '55': 'MTN', '59': 'MTN',
        '20': 'VOD', '50': 'VOD',
        '27': 'AIR', '57': 'AIR', '26': 'AIR', '56': 'AIR',
    }
    return prefix_map.get(cleaned[:2], 'UNK')


def generate_signature(payload, secret_key=None):
    """Generate HMAC-SHA256 signature."""
    key = (secret_key or settings.ORCHARD_SECRET_KEY).encode('utf-8')
    message = json.dumps(payload)
    return hmac.new(key, message.encode('utf-8'), hashlib.sha256).hexdigest()


def normalize_phone(phone):
    """Normalize phone to 0XXXXXXXXX format."""
    cleaned = re.sub(r'\D', '', phone)
    if cleaned.startswith('233'):
        cleaned = '0' + cleaned[3:]
    elif not cleaned.startswith('0'):
        cleaned = '0' + cleaned
    return cleaned


# ==================== Mobile Money Name Verification ====================

def verify_mobile_money_name(mobile_number):
    """
    Verify mobile money account name via Orchard AII through ky3mp3 proxy.
    Critical for fraud prevention: ensures users see verified names before confirming.
    """
    cleaned = re.sub(r'\D', '', mobile_number)
    if cleaned.startswith('233'):
        cleaned = cleaned[3:]
    if cleaned.startswith('0'):
        cleaned = cleaned[1:]

    network = detect_network(mobile_number)
    bank_code = {'MTN': 'MTN', 'VOD': 'VOD', 'AIR': 'AIR'}.get(network, 'UNK')

    if bank_code == 'UNK':
        return {'success': False, 'name': None, 'network': network, 'message': 'Unable to detect network'}

    api_number = '0' + cleaned
    timestamp = datetime.now(dt_timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "customer_number": api_number,
        "exttrid": f"CFV{int(time.time())}",
        "service_id": settings.ORCHARD_SERVICE_ID,
        "nw": "BNK",
        "bank_code": bank_code,
        "trans_type": "AII",
        "ts": timestamp,
    }

    signature = generate_signature(payload)
    headers = {
        'Authorization': f'{settings.ORCHARD_CLIENT_ID}:{signature}',
        'Content-Type': 'application/json',
    }

    try:
        proxy_body = {"headers": headers, "payload": payload}
        response = requests.post(
            settings.ORCHARD_API_URL,
            json=proxy_body,
            headers={'Content-Type': 'application/json'},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        logger.info(f'Momo verification response: {data}')

        if data.get('resp_code') == '027':
            return {
                'success': True,
                'name': data.get('name', 'Unknown'),
                'network': network,
                'message': 'Verification successful',
            }
        return {
            'success': False,
            'name': None,
            'network': network,
            'message': data.get('resp_desc', 'Verification failed'),
        }

    except requests.exceptions.RequestException as e:
        logger.error(f'Momo verification error: {e}')
        return {'success': False, 'name': None, 'network': network, 'message': 'Verification service unavailable.'}
    except Exception as e:
        logger.error(f'Unexpected momo verification error: {e}')
        return {'success': False, 'name': None, 'network': network, 'message': 'Verification failed'}


# ==================== Payment Status Checks (via proxy) ====================

def check_deposit_status(reference):
    """Check CTM deposit status via Orchard verification proxy."""
    payload = {
        "exttrid": reference,
        "service_id": settings.ORCHARD_SERVICE_ID,
        "trans_type": "CTM",
    }
    signature = generate_signature(payload)
    headers = {
        'Authorization': f'{settings.ORCHARD_CLIENT_ID}:{signature}',
        'Content-Type': 'application/json',
    }
    proxy_data = {"headers": headers, "payload": payload, "endpoint": "checkTransaction"}
    verification_url = settings.ORCHARD_PROXY_URL

    try:
        response = requests.post(verification_url, json=proxy_data, timeout=30)
        if response.status_code not in (200, 401):
            logger.warning(f'CTM status check proxy returned HTTP {response.status_code} for {reference}')
        data = response.json()
        logger.info(f'CTM status check for {reference}: {data}')

        trans_status = data.get('trans_status', '').upper()
        resp_code = data.get('resp_code', '')
        resp_desc = data.get('resp_desc', data.get('message', ''))
        main_code = trans_status.split('/')[0] if trans_status else ''

        if main_code == '000' or resp_code == '000' or resp_desc.upper() == 'SUCCESSFUL':
            return {'success': True, 'status': 'SUCCESSFUL', 'message': resp_desc or 'Payment successful', 'data': data}
        elif resp_code in ['034', '099', '100', '101', '102', '103', '104', '105']:
            return {'success': True, 'status': 'FAILED', 'message': resp_desc or 'Payment failed', 'data': data}
        elif main_code == '001' and 'TIMEOUT' in trans_status:
            return {'success': True, 'status': 'FAILED', 'message': resp_desc or 'Payment timed out', 'data': data}
        elif main_code == '001' and 'FAILED' in trans_status:
            return {'success': True, 'status': 'FAILED', 'message': resp_desc or 'Payment failed', 'data': data}
        elif resp_code == '084' or main_code == '001':
            return {'success': True, 'status': 'PENDING', 'message': resp_desc or 'Still processing', 'data': data}
        return {'success': True, 'status': 'UNKNOWN', 'message': resp_desc or f'Unknown: {trans_status or resp_code}', 'data': data}

    except Exception as e:
        logger.error(f'CTM status check error for {reference}: {e}')
        return {'success': False, 'status': 'ERROR', 'message': str(e), 'data': {}}


def check_payout_status(reference, use_wanaown=True):
    """Check MTC payout status via Orchard verification proxy."""
    if use_wanaown:
        service_id = getattr(settings, 'ORCHARD_SERVICE_ID_WANAOWN', '') or settings.ORCHARD_SERVICE_ID
        client_id = getattr(settings, 'ORCHARD_CLIENT_ID_WANAOWN', '') or settings.ORCHARD_CLIENT_ID
        secret_key = getattr(settings, 'ORCHARD_SECRET_KEY_WANAOWN', '') or settings.ORCHARD_SECRET_KEY
    else:
        service_id = settings.ORCHARD_SERVICE_ID
        client_id = settings.ORCHARD_CLIENT_ID
        secret_key = settings.ORCHARD_SECRET_KEY

    payload = {
        "exttrid": reference,
        "service_id": service_id,
        "trans_type": "MTC",
    }
    signature = generate_signature(payload, secret_key)
    headers = {
        'Authorization': f'{client_id}:{signature}',
        'Content-Type': 'application/json',
    }
    proxy_data = {"headers": headers, "payload": payload, "endpoint": "checkTransaction"}
    verification_url = settings.ORCHARD_PROXY_URL

    try:
        response = requests.post(verification_url, json=proxy_data, timeout=30)
        data = response.json()
        logger.info(f'MTC status check for {reference}: {data}')

        trans_status = data.get('trans_status', '').upper()
        resp_code = data.get('resp_code', '')
        resp_desc = data.get('resp_desc', data.get('message', ''))
        main_code = trans_status.split('/')[0] if trans_status else ''
        sub_code = trans_status.split('/')[1] if '/' in trans_status else ''

        failure_sub_codes = ['034', '035', '036', '037', '039', '040', '041', '042']

        if main_code == '000' or resp_code == '000' or resp_desc.upper() == 'SUCCESSFUL':
            return {'success': True, 'status': 'SUCCESSFUL', 'message': resp_desc or 'Payout successful', 'data': data}
        elif resp_code in ['034', '099', '100', '101', '102', '103', '104', '105']:
            return {'success': True, 'status': 'FAILED', 'message': resp_desc or 'Payout failed', 'data': data}
        elif main_code == '001' and sub_code in failure_sub_codes:
            return {'success': True, 'status': 'FAILED', 'message': resp_desc or f'Failed: {trans_status}', 'data': data}
        elif main_code == '001' and sub_code == '038':
            return {'success': True, 'status': 'DELAYED', 'message': resp_desc or 'Temporarily delayed', 'data': data}
        elif resp_code == '084' or main_code == '001':
            return {'success': True, 'status': 'PENDING', 'message': resp_desc or 'Still processing', 'data': data}
        return {'success': True, 'status': 'UNKNOWN', 'message': resp_desc or f'Unknown: {trans_status or resp_code}', 'data': data}

    except Exception as e:
        logger.error(f'MTC status check error for {reference}: {e}')
        return {'success': False, 'status': 'ERROR', 'message': str(e), 'data': {}}


# ==================== Deposit: Mobile Money (CTM) ====================

def initiate_mobile_money_deposit(player, amount, mobile_number, network=None):
    """
    Initiate mobile money deposit via Orchard CTM.
    Returns: (success, deposit_instance_or_error)
    """
    from payments.models import Deposit

    if not network:
        network = detect_network(mobile_number)

    if network == 'UNK':
        return False, 'Could not detect network. Please select manually.'

    payment_ref = f'{settings.PAYMENT_PREFIX_DEPOSIT}{uuid.uuid4().hex[:8].upper()}'
    normalized = normalize_phone(mobile_number)
    timestamp = datetime.now(dt_timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    deposit = Deposit.objects.create(
        player=player,
        amount=amount,
        currency_code='GHS',
        method='mobile_money',
        status='pending',
        orchard_reference=payment_ref,
        mobile_number=normalized,
        network=network,
    )

    orchard_payload = {
        "customer_number": normalized,
        "amount": f"{float(amount):.2f}",
        "exttrid": payment_ref,
        "reference": "Cashflip Deposit"[:25],
        "nw": network,
        "trans_type": "CTM",
        "callback_url": settings.ORCHARD_CALLBACK_URL,
        "service_id": settings.ORCHARD_SERVICE_ID,
        "ts": timestamp,
    }

    signature = generate_signature(orchard_payload)
    api_headers = {
        'Authorization': f'{settings.ORCHARD_CLIENT_ID}:{signature}',
        'Content-Type': 'application/json',
    }

    proxy_body = {"headers": api_headers, "payload": orchard_payload}

    try:
        response = requests.post(
            settings.ORCHARD_API_URL,
            json=proxy_body,
            headers={'Content-Type': 'application/json'},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        deposit.orchard_response = data
        deposit.save(update_fields=['orchard_response'])

        success_codes = ['015', '0000', '027', '00']
        resp_code = data.get('resp_code') or data.get('responseCode')

        if response.status_code == 200 and resp_code in success_codes:
            deposit.status = 'processing'
            deposit.save(update_fields=['status'])
            logger.info(f'Deposit initiated: {payment_ref}')
            return True, deposit
        else:
            error_msg = data.get('resp_desc') or data.get('message', 'Deposit initiation failed')
            deposit.status = 'failed'
            deposit.failure_reason = error_msg
            deposit.save(update_fields=['status', 'failure_reason'])
            return False, error_msg

    except requests.exceptions.RequestException as e:
        logger.error(f'Orchard deposit error: {e}')
        deposit.status = 'failed'
        deposit.failure_reason = str(e)
        deposit.save(update_fields=['status', 'failure_reason'])
        return False, 'Payment service temporarily unavailable.'


# ==================== Deposit: Card (Paystack) ====================

def initiate_card_deposit(player, amount):
    """
    Initiate card deposit via Paystack.
    Returns: (success, result_dict_or_error)
    """
    from payments.models import Deposit

    payment_ref = f'{settings.PAYMENT_PREFIX_PAYSTACK}{uuid.uuid4().hex[:8].upper()}'

    deposit = Deposit.objects.create(
        player=player,
        amount=amount,
        currency_code='GHS',
        method='card',
        status='pending',
        paystack_reference=payment_ref,
    )

    paystack_url = "https://api.paystack.co/transaction/initialize"
    headers = {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
    }

    payload = {
        'email': player.email or f'player_{player.id}@cashflip.game',
        'amount': int(float(amount) * 100),  # kobo
        'reference': payment_ref,
        'callback_url': settings.PAYSTACK_CALLBACK_URL,
        'channels': ['card'],
        'metadata': {
            'player_id': str(player.id),
            'type': 'cashflip_deposit',
        },
    }

    try:
        response = requests.post(paystack_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get('status') and data.get('data'):
            pdata = data['data']
            deposit.paystack_authorization_url = pdata.get('authorization_url', '')
            deposit.paystack_response = data
            deposit.status = 'processing'
            deposit.save(update_fields=['paystack_authorization_url', 'paystack_response', 'status'])

            return True, {
                'authorization_url': pdata.get('authorization_url'),
                'reference': payment_ref,
                'deposit_id': str(deposit.id),
            }
        else:
            error_msg = data.get('message', 'Card payment initialization failed')
            deposit.status = 'failed'
            deposit.failure_reason = error_msg
            deposit.save(update_fields=['status', 'failure_reason'])
            return False, error_msg

    except requests.exceptions.RequestException as e:
        logger.error(f'Paystack deposit error: {e}')
        deposit.status = 'failed'
        deposit.failure_reason = str(e)
        deposit.save(update_fields=['status', 'failure_reason'])
        return False, 'Payment service temporarily unavailable.'


# ==================== Withdrawal: MTC Payout ====================

def initiate_withdrawal(player, amount, mobile_number, network=None):
    """
    Initiate withdrawal/payout via Orchard MTC.
    Returns: (success, withdrawal_or_error)
    """
    from payments.models import Withdrawal

    if not network:
        network = detect_network(mobile_number)

    normalized = normalize_phone(mobile_number)
    payout_ref = f'{settings.PAYMENT_PREFIX_PAYOUT}{uuid.uuid4().hex[:8].upper()}'
    ext_trid = f'{settings.PAYMENT_PREFIX_PAYOUT}{int(time.time())}-{payout_ref[-8:]}'
    timestamp = datetime.now(dt_timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    withdrawal = Withdrawal.objects.create(
        player=player,
        amount=amount,
        currency_code='GHS',
        mobile_number=normalized,
        network=network,
        status='pending',
        payout_reference=payout_ref,
        payout_ext_trid=ext_trid,
    )

    api_url = getattr(settings, 'ORCHARD_API_URL_WANAOWN', '') or settings.ORCHARD_API_URL
    client_id = getattr(settings, 'ORCHARD_CLIENT_ID_WANAOWN', '') or settings.ORCHARD_CLIENT_ID
    secret_key = getattr(settings, 'ORCHARD_SECRET_KEY_WANAOWN', '') or settings.ORCHARD_SECRET_KEY
    service_id = getattr(settings, 'ORCHARD_SERVICE_ID_WANAOWN', '') or settings.ORCHARD_SERVICE_ID
    callback_url = getattr(settings, 'ORCHARD_CALLBACK_URL_WANAOWN', '') or settings.ORCHARD_CALLBACK_URL

    payload = {
        "customer_number": normalized,
        "amount": str(float(amount)),
        "exttrid": ext_trid,
        "reference": payout_ref[:25],
        "service_id": service_id,
        "nw": network,
        "trans_type": "MTC",
        "ts": timestamp,
        "callback_url": callback_url,
    }

    signature = generate_signature(payload, secret_key)
    headers = {
        'Authorization': f'{client_id}:{signature}',
        'Content-Type': 'application/json',
    }

    proxy_body = {"headers": headers, "payload": payload}

    try:
        response = requests.post(
            api_url, json=proxy_body,
            headers={'Content-Type': 'application/json'}, timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        withdrawal.orchard_response = data
        resp_code = str(data.get('resp_code', '')).upper()
        completed_codes = ['0000', '00', '000']
        processing_codes = ['015', '027']

        if resp_code in completed_codes:
            withdrawal.status = 'completed'
            withdrawal.completed_at = timezone.now()
        elif resp_code in processing_codes:
            withdrawal.status = 'processing'
        else:
            withdrawal.status = 'failed'
            withdrawal.failure_reason = data.get('resp_desc', 'Payout failed')

        withdrawal.save()
        success = withdrawal.status in ['completed', 'processing']
        return success, withdrawal if success else withdrawal.failure_reason

    except Exception as e:
        logger.error(f'Withdrawal error: {e}')
        withdrawal.status = 'failed'
        withdrawal.failure_reason = str(e)
        withdrawal.save()
        return False, 'Withdrawal service temporarily unavailable.'


# ==================== Webhook Handlers ====================

def process_orchard_callback(reference, trans_status, resp_code, data):
    """Process Orchard callback for deposits and withdrawals."""
    from payments.models import Deposit, Withdrawal
    from wallet.models import Wallet, WalletTransaction

    logger.info(f'Orchard callback: ref={reference}, status={trans_status}, code={resp_code}')

    # Deposit callback
    if reference.startswith(settings.PAYMENT_PREFIX_DEPOSIT):
        deposit = Deposit.objects.filter(orchard_reference=reference).first()
        if not deposit:
            logger.warning(f'Deposit not found: {reference}')
            return False

        if deposit.status == 'completed':
            return True

        deposit.orchard_response = data

        if resp_code in ['000', '0000', '00'] or trans_status.startswith('000'):
            deposit.status = 'completed'
            deposit.completed_at = timezone.now()
            deposit.save()
            _credit_wallet(deposit.player, deposit.amount, f'CF-WDEP-{reference[-8:]}', 'deposit')
            return True
        else:
            deposit.status = 'failed'
            deposit.failure_reason = data.get('resp_desc', 'Payment failed')
            deposit.save()
            return True

    # Withdrawal callback
    if reference.startswith(settings.PAYMENT_PREFIX_PAYOUT):
        withdrawal = Withdrawal.objects.filter(payout_ext_trid=reference).first()
        if not withdrawal:
            withdrawal = Withdrawal.objects.filter(payout_reference=reference).first()
        if not withdrawal:
            logger.warning(f'Withdrawal not found: {reference}')
            return False

        if withdrawal.status == 'completed':
            return True

        withdrawal.orchard_response = data

        if resp_code in ['000', '0000', '00'] or trans_status.startswith('000'):
            withdrawal.status = 'completed'
            withdrawal.completed_at = timezone.now()
        else:
            withdrawal.status = 'failed'
            withdrawal.failure_reason = data.get('resp_desc', 'Payout failed')
            # Refund wallet
            _credit_wallet(withdrawal.player, withdrawal.amount, f'CF-WREF-{reference[-8:]}', 'admin_credit')

        withdrawal.save()
        return True

    return False


def process_paystack_webhook(webhook_data):
    """Process Paystack webhook for card deposits."""
    from payments.models import Deposit

    event = webhook_data.get('event')
    data = webhook_data.get('data', {})
    reference = data.get('reference', '')

    if not reference.startswith(settings.PAYMENT_PREFIX_PAYSTACK):
        return False

    deposit = Deposit.objects.filter(paystack_reference=reference).first()
    if not deposit:
        logger.warning(f'Deposit not found for Paystack ref: {reference}')
        return False

    if event == 'charge.success':
        if deposit.status == 'completed':
            return True
        deposit.status = 'completed'
        deposit.paystack_response = webhook_data
        deposit.completed_at = timezone.now()
        deposit.save()
        _credit_wallet(deposit.player, deposit.amount, f'CF-WDEP-{reference[-8:]}', 'deposit')
        return True

    elif event == 'charge.failed':
        deposit.status = 'failed'
        deposit.failure_reason = data.get('gateway_response', 'Payment failed')
        deposit.paystack_response = webhook_data
        deposit.save()
        return True

    return True


def _credit_wallet(player, amount, reference, tx_type='deposit'):
    """Credit player wallet after successful deposit."""
    from wallet.models import Wallet, WalletTransaction
    from game.models import Currency
    from django.db import transaction

    with transaction.atomic():
        wallet, created = Wallet.objects.get_or_create(
            player=player,
            defaults={'currency': Currency.objects.filter(is_default=True).first() or Currency.objects.first()}
        )
        balance_before = wallet.balance
        wallet.balance += Decimal(str(amount))
        wallet.save(update_fields=['balance', 'updated_at'])

        WalletTransaction.objects.create(
            wallet=wallet,
            amount=Decimal(str(amount)),
            tx_type=tx_type,
            reference=reference,
            balance_before=balance_before,
            balance_after=wallet.balance,
        )

    # Update profile
    from accounts.models import PlayerProfile
    profile, _ = PlayerProfile.objects.get_or_create(player=player)
    profile.total_deposited += Decimal(str(amount))
    profile.save(update_fields=['total_deposited', 'updated_at'])

    # Check referral qualification
    _check_referral_qualification(player, amount)


def _check_referral_qualification(player, deposit_amount):
    """Check if this deposit qualifies a pending referral."""
    try:
        from referrals.models import Referral, ReferralConfig, ReferralCode
        config = ReferralConfig.get_config()
        if not config.is_enabled:
            return

        referral = Referral.objects.filter(referee=player, status='pending').first()
        if not referral:
            return

        if Decimal(str(deposit_amount)) >= config.min_deposit_to_qualify:
            referral.status = 'qualified'
            referral.qualified_at = timezone.now()
            referral.save()

            # Pay bonuses
            _pay_referral_bonuses(referral, config)
    except Exception as e:
        logger.error(f'Referral qualification error: {e}')


def _pay_referral_bonuses(referral, config):
    """Pay referral bonuses to referrer and referee."""
    from wallet.models import Wallet, WalletTransaction
    from referrals.models import ReferralCode
    from game.models import Currency
    from django.db import transaction

    default_currency = Currency.objects.filter(is_default=True).first()

    with transaction.atomic():
        # Pay referrer
        if not referral.referrer_bonus_paid and config.referrer_bonus > 0:
            r_wallet, _ = Wallet.objects.get_or_create(
                player=referral.referrer,
                defaults={'currency': default_currency}
            )
            balance_before = r_wallet.balance
            r_wallet.balance += config.referrer_bonus
            r_wallet.save(update_fields=['balance', 'updated_at'])
            WalletTransaction.objects.create(
                wallet=r_wallet,
                amount=config.referrer_bonus,
                tx_type='referral_bonus',
                reference=f'CF-REF-{uuid.uuid4().hex[:8].upper()}',
                balance_before=balance_before,
                balance_after=r_wallet.balance,
                metadata={'referee': str(referral.referee.id)},
            )
            referral.referrer_bonus_paid = True

            # Update referral code stats
            ref_code = ReferralCode.objects.filter(player=referral.referrer).first()
            if ref_code:
                ref_code.total_referrals += 1
                ref_code.total_earned += config.referrer_bonus
                ref_code.save(update_fields=['total_referrals', 'total_earned'])

        # Pay referee
        if not referral.referee_bonus_paid and config.referee_bonus > 0:
            e_wallet, _ = Wallet.objects.get_or_create(
                player=referral.referee,
                defaults={'currency': default_currency}
            )
            balance_before = e_wallet.balance
            e_wallet.balance += config.referee_bonus
            e_wallet.save(update_fields=['balance', 'updated_at'])
            WalletTransaction.objects.create(
                wallet=e_wallet,
                amount=config.referee_bonus,
                tx_type='referral_bonus',
                reference=f'CF-REF-{uuid.uuid4().hex[:8].upper()}',
                balance_before=balance_before,
                balance_after=e_wallet.balance,
                metadata={'referrer': str(referral.referrer.id)},
            )
            referral.referee_bonus_paid = True

        referral.status = 'paid'
        referral.save()

    logger.info(f'Referral bonuses paid: {referral.referrer} -> {referral.referee}')
