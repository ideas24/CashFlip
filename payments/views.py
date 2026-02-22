"""
Payment API Views & Webhook Handlers

Security:
- Mobile money name verification via Orchard AII before any deposit/withdrawal
- Strict name matching: deposit momo name = payout account
- All Orchard API calls go through whitelisted ky3mp3 proxy
"""

import json
import hmac
import hashlib
import logging
import uuid

from django.conf import settings
from django.db import transaction as db_transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from payments.models import MobileMoneyAccount
from payments.services import (
    initiate_mobile_money_deposit, initiate_card_deposit, initiate_withdrawal,
    process_orchard_callback, process_paystack_webhook, validate_mobile_number,
    detect_network, normalize_phone, verify_mobile_money_name,
    check_deposit_status, check_payout_status,
)

logger = logging.getLogger(__name__)


class VerificationThrottle(UserRateThrottle):
    rate = '5/min'


class DepositThrottle(UserRateThrottle):
    rate = '10/min'


class WithdrawThrottle(UserRateThrottle):
    rate = '5/min'


class AddAccountThrottle(UserRateThrottle):
    rate = '5/min'


# ==================== Mobile Money Verification ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([VerificationThrottle])
def verify_momo(request):
    """
    Verify a mobile money account name via Orchard AII.
    Players must verify before deposit or adding a payment method.
    Returns the verified account holder name.
    """
    mobile_number = request.data.get('mobile_number')
    if not mobile_number:
        return Response({'error': 'Mobile number required'}, status=status.HTTP_400_BAD_REQUEST)

    if not validate_mobile_number(mobile_number):
        return Response({'error': 'Invalid Ghanaian mobile number'}, status=status.HTTP_400_BAD_REQUEST)

    result = verify_mobile_money_name(mobile_number)
    if result['success']:
        return Response({
            'success': True,
            'name': result['name'],
            'network': result['network'],
            'mobile_number': normalize_phone(mobile_number),
        })
    return Response({'error': result['message']}, status=status.HTTP_400_BAD_REQUEST)


# ==================== Payment Method Management ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_momo_accounts(request):
    """List player's verified mobile money accounts."""
    accounts = MobileMoneyAccount.objects.filter(player=request.user, is_active=True)
    data = [{
        'id': str(a.id),
        'mobile_number': a.mobile_number,
        'network': a.network,
        'verified_name': a.verified_name,
        'is_primary': a.is_primary,
    } for a in accounts]
    return Response({'accounts': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([VerificationThrottle])
def add_momo_account(request):
    """
    Add a verified mobile money payment method.
    Step 1: Caller provides mobile_number.
    Step 2: We verify the name via Orchard AII.
    Step 3: If player already has accounts, the new account name must STRICTLY
            match existing verified names to prevent impersonation.
    """
    mobile_number = request.data.get('mobile_number')
    if not mobile_number:
        return Response({'error': 'Mobile number required'}, status=status.HTTP_400_BAD_REQUEST)

    if not validate_mobile_number(mobile_number):
        return Response({'error': 'Invalid Ghanaian mobile number'}, status=status.HTTP_400_BAD_REQUEST)

    normalized = normalize_phone(mobile_number)

    # Check if already added
    existing = MobileMoneyAccount.objects.filter(
        player=request.user, mobile_number=normalized, is_active=True
    ).first()
    if existing:
        return Response({
            'success': True,
            'message': 'Account already registered',
            'account': {
                'id': str(existing.id),
                'mobile_number': existing.mobile_number,
                'network': existing.network,
                'verified_name': existing.verified_name,
                'is_primary': existing.is_primary,
            }
        })

    # Max 3 accounts per player
    existing_accounts = MobileMoneyAccount.objects.filter(
        player=request.user, is_active=True
    )
    if existing_accounts.count() >= 3:
        return Response(
            {'error': 'Maximum 3 mobile money accounts allowed. Remove one to add a new account.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Verify name via Orchard AII
    result = verify_mobile_money_name(mobile_number)
    if not result['success']:
        return Response({'error': result['message']}, status=status.HTTP_400_BAD_REQUEST)

    verified_name = result['name'].strip().upper()
    network = result['network']

    # SECURITY: Strict exact full name matching against existing accounts
    if existing_accounts.exists():
        existing_name = existing_accounts.first().verified_name.strip().upper()
        if verified_name != existing_name:
            logger.warning(
                f'Name mismatch for player {request.user.id}: '
                f'existing="{existing_name}", new="{verified_name}" ({normalized})'
            )
            return Response({
                'error': f'Account name "{result["name"]}" does not match your '
                         f'registered name "{existing_accounts.first().verified_name}". '
                         f'All payment accounts must be in the same name for security.'
            }, status=status.HTTP_403_FORBIDDEN)

    # Create the account
    is_primary = not existing_accounts.exists()
    account = MobileMoneyAccount.objects.create(
        player=request.user,
        mobile_number=normalized,
        network=network,
        verified_name=result['name'],
        is_primary=is_primary,
    )

    return Response({
        'success': True,
        'message': 'Payment method added successfully',
        'account': {
            'id': str(account.id),
            'mobile_number': account.mobile_number,
            'network': account.network,
            'verified_name': account.verified_name,
            'is_primary': account.is_primary,
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_primary_momo(request):
    """Set a mobile money account as primary."""
    account_id = request.data.get('account_id')
    if not account_id:
        return Response({'error': 'account_id required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        account = MobileMoneyAccount.objects.get(
            id=account_id, player=request.user, is_active=True
        )
    except MobileMoneyAccount.DoesNotExist:
        return Response({'error': 'Account not found'}, status=status.HTTP_404_NOT_FOUND)

    account.is_primary = True
    account.save()
    return Response({'success': True, 'message': 'Primary account updated'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def remove_momo_account(request):
    """Deactivate a mobile money account (soft delete). Cannot remove the only account."""
    account_id = request.data.get('account_id')
    if not account_id:
        return Response({'error': 'account_id required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        account = MobileMoneyAccount.objects.get(
            id=account_id, player=request.user, is_active=True
        )
    except MobileMoneyAccount.DoesNotExist:
        return Response({'error': 'Account not found'}, status=status.HTTP_404_NOT_FOUND)

    active_count = MobileMoneyAccount.objects.filter(player=request.user, is_active=True).count()
    if active_count <= 1:
        return Response({'error': 'Cannot remove your only payment method'}, status=status.HTTP_400_BAD_REQUEST)

    if account.is_primary:
        return Response(
            {'error': 'Cannot remove your primary account. Switch primary to another account first.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    account.is_active = False
    account.save(update_fields=['is_active'])

    return Response({'success': True, 'message': 'Account removed'})


# ==================== Deposits ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([DepositThrottle])
def deposit_mobile_money(request):
    """
    Initiate mobile money deposit.
    The mobile number must be a verified MobileMoneyAccount.
    Players see the verified name before confirming.
    """
    amount = request.data.get('amount')
    account_id = request.data.get('account_id')
    mobile_number = request.data.get('mobile_number')

    if not amount:
        return Response({'error': 'Amount required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

    # Resolve the momo account
    if account_id:
        try:
            account = MobileMoneyAccount.objects.get(
                id=account_id, player=request.user, is_active=True
            )
        except MobileMoneyAccount.DoesNotExist:
            return Response({'error': 'Payment method not found'}, status=status.HTTP_404_NOT_FOUND)
        mobile_number = account.mobile_number
        network = account.network
    elif mobile_number:
        if not validate_mobile_number(mobile_number):
            return Response({'error': 'Invalid mobile number'}, status=status.HTTP_400_BAD_REQUEST)
        normalized = normalize_phone(mobile_number)
        account = MobileMoneyAccount.objects.filter(
            player=request.user, mobile_number=normalized, is_active=True
        ).first()
        if not account:
            return Response(
                {'error': 'This number is not a verified payment method. Please verify it first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        mobile_number = account.mobile_number
        network = account.network
    else:
        # Use primary account
        account = MobileMoneyAccount.objects.filter(
            player=request.user, is_primary=True, is_active=True
        ).first()
        if not account:
            return Response(
                {'error': 'No payment method found. Please add a mobile money account first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        mobile_number = account.mobile_number
        network = account.network

    success, result = initiate_mobile_money_deposit(request.user, amount, mobile_number, network)

    if success:
        return Response({
            'success': True,
            'message': f'Payment prompt sent to {mobile_number} ({account.verified_name})',
            'reference': result.orchard_reference,
            'deposit_id': str(result.id),
            'verified_name': account.verified_name,
        })
    return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([DepositThrottle])
def deposit_card(request):
    """Initiate card deposit via Paystack."""
    amount = request.data.get('amount')

    if not amount:
        return Response({'error': 'Amount required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

    success, result = initiate_card_deposit(request.user, amount)

    if success:
        return Response({'success': True, **result})
    return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)


# ==================== Withdrawals ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([WithdrawThrottle])
def withdraw(request):
    """
    Initiate withdrawal to mobile money.
    MUST use a verified MobileMoneyAccount — same name as deposit account.
    """
    # Check if withdrawals are paused
    from game.models import GameConfig
    game_config = GameConfig.objects.first()
    if game_config and not game_config.withdrawal_enabled:
        msg = game_config.withdrawal_paused_message or 'Withdrawals are temporarily paused. Your balance is safe.'
        return Response({'error': msg, 'withdrawal_paused': True}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    amount = request.data.get('amount')
    account_id = request.data.get('account_id')

    if not amount:
        return Response({'error': 'Amount required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        from decimal import Decimal, InvalidOperation
        amount = Decimal(str(amount))
    except (ValueError, TypeError, InvalidOperation):
        return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

    # Resolve the payout account
    if account_id:
        try:
            account = MobileMoneyAccount.objects.get(
                id=account_id, player=request.user, is_active=True
            )
        except MobileMoneyAccount.DoesNotExist:
            return Response({'error': 'Payment method not found'}, status=status.HTTP_404_NOT_FOUND)
    else:
        # Use primary account
        account = MobileMoneyAccount.objects.filter(
            player=request.user, is_primary=True, is_active=True
        ).first()
        if not account:
            return Response(
                {'error': 'No payout account found. Please add a mobile money account first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Check wallet balance
    from wallet.models import Wallet, WalletTransaction
    try:
        wallet = Wallet.objects.get(player=request.user)
    except Wallet.DoesNotExist:
        return Response({'error': 'Wallet not found'}, status=status.HTTP_400_BAD_REQUEST)

    if wallet.available_balance < amount:
        return Response({'error': 'Insufficient balance'}, status=status.HTTP_400_BAD_REQUEST)

    # Deduct from wallet first
    with db_transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(player=request.user)
        balance_before = wallet.balance
        wallet.balance -= amount
        wallet.save(update_fields=['balance', 'updated_at'])

        WalletTransaction.objects.create(
            wallet=wallet,
            amount=-amount,
            tx_type='withdrawal',
            reference=f'CF-WDRAW-{uuid.uuid4().hex[:8].upper()}',
            status='pending',
            balance_before=balance_before,
            balance_after=wallet.balance,
        )

    success, result = initiate_withdrawal(
        request.user, amount, account.mobile_number, account.network
    )

    if success:
        return Response({
            'success': True,
            'message': f'Withdrawal processing to {account.mobile_number} ({account.verified_name})',
            'reference': result.payout_reference,
            'verified_name': account.verified_name,
        })
    return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)


# ==================== Wallet & History ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_balance(request):
    """Get wallet balance."""
    from wallet.models import Wallet
    try:
        wallet = Wallet.objects.get(player=request.user)
        return Response({
            'balance': str(wallet.balance),
            'available_balance': str(wallet.available_balance),
            'locked_balance': str(wallet.locked_balance),
            'currency': wallet.currency.code,
            'currency_symbol': wallet.currency.symbol,
        })
    except Wallet.DoesNotExist:
        return Response({
            'balance': '0.00',
            'available_balance': '0.00',
            'locked_balance': '0.00',
            'currency': 'GHS',
            'currency_symbol': 'GH₵',
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_history(request):
    """Get wallet transaction history."""
    from wallet.models import Wallet, WalletTransaction
    try:
        wallet = Wallet.objects.get(player=request.user)
        txs = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')[:50]
        data = [{
            'id': str(tx.id),
            'amount': str(tx.amount),
            'type': tx.tx_type,
            'status': tx.status,
            'reference': tx.reference,
            'created_at': tx.created_at.isoformat(),
        } for tx in txs]
        return Response(data)
    except Wallet.DoesNotExist:
        return Response([])


# ==================== Payment Status ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def deposit_status(request, reference):
    """Check deposit payment status via Orchard verification proxy."""
    from payments.models import Deposit
    deposit = Deposit.objects.filter(
        orchard_reference=reference, player=request.user
    ).first()
    if not deposit:
        return Response({'error': 'Deposit not found'}, status=status.HTTP_404_NOT_FOUND)

    if deposit.status in ['completed', 'failed']:
        return Response({'status': deposit.status, 'message': deposit.failure_reason or 'Done'})

    result = check_deposit_status(reference)
    poll_status = result.get('status', 'UNKNOWN')

    # If polling detects a terminal state, update the deposit record
    # so we don't keep polling (in case the webhook was missed or delayed)
    if poll_status == 'SUCCESSFUL' and deposit.status != 'completed':
        from django.utils import timezone as tz
        deposit.status = 'completed'
        deposit.completed_at = tz.now()
        deposit.orchard_response = result.get('data', {})
        deposit.save(update_fields=['status', 'completed_at', 'orchard_response'])
        from payments.services import _credit_wallet
        _credit_wallet(deposit.player, deposit.amount, f'CF-WDEP-{reference[-8:]}', 'deposit')
    elif poll_status == 'FAILED' and deposit.status not in ('completed', 'failed'):
        deposit.status = 'failed'
        deposit.failure_reason = result.get('message', 'Payment failed')
        deposit.orchard_response = result.get('data', {})
        deposit.save(update_fields=['status', 'failure_reason', 'orchard_response'])

    return Response({
        'status': poll_status,
        'message': result.get('message', ''),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def withdrawal_status(request, reference):
    """Check withdrawal payout status via Orchard verification proxy."""
    from django.db.models import Q
    from payments.models import Withdrawal
    withdrawal = Withdrawal.objects.filter(
        player=request.user
    ).filter(
        Q(payout_reference=reference) | Q(payout_ext_trid=reference)
    ).first()
    if not withdrawal:
        return Response({'error': 'Withdrawal not found'}, status=status.HTTP_404_NOT_FOUND)

    if withdrawal.status in ['completed', 'failed']:
        return Response({'status': withdrawal.status, 'message': withdrawal.failure_reason or 'Done'})

    result = check_payout_status(withdrawal.payout_ext_trid)
    return Response({
        'status': result.get('status', 'UNKNOWN'),
        'message': result.get('message', ''),
    })


# ==================== Webhooks ====================

@csrf_exempt
@require_POST
def orchard_webhook(request):
    """Handle Orchard payment/payout callbacks."""
    try:
        data = json.loads(request.body)
        logger.info(f'Orchard webhook: {data}')

        reference = data.get('exttrid') or data.get('trans_ref') or data.get('reference')
        trans_status = data.get('trans_status', '')
        resp_code = data.get('resp_code') or data.get('responseCode', '')

        if not reference:
            return JsonResponse({'error': 'Missing reference'}, status=400)

        success = process_orchard_callback(reference, trans_status, resp_code, data)
        return JsonResponse({'status': 'success' if success else 'failed'})
    except Exception as e:
        logger.error(f'Orchard webhook error: {e}')
        return JsonResponse({'error': 'Processing failed'}, status=500)


@csrf_exempt
def paystack_success(request):
    """Paystack success callback — proxy router redirects here after successful payment."""
    reference = request.GET.get('reference', '')
    logger.info(f'Paystack success callback: {reference}')

    from payments.models import Deposit

    deposit = None
    if reference:
        deposit = Deposit.objects.filter(paystack_reference=reference).first()

    if deposit and deposit.status == 'completed':
        amount = deposit.amount
        return JsonResponse({'status': 'success', 'message': f'Payment of GHS {amount} received.', 'reference': reference})

    # If not yet completed, try verifying with Paystack now
    if deposit and deposit.status in ('pending', 'processing'):
        success = process_paystack_webhook({
            'event': 'charge.success',
            'data': {'reference': reference, 'status': 'success'},
        })
        if success:
            deposit.refresh_from_db()
            return JsonResponse({'status': 'success', 'message': f'Payment of GHS {deposit.amount} received.', 'reference': reference})

    return JsonResponse({'status': 'pending', 'message': 'Payment is being processed.', 'reference': reference})


class TransferThrottle(UserRateThrottle):
    rate = '5/min'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([TransferThrottle])
def transfer_to_player(request):
    """
    Transfer funds from your wallet to another player by phone number.
    Casino-style peer transfer with min/max limits.
    """
    from accounts.models import Player
    from wallet.models import Wallet, WalletTransaction

    phone = request.data.get('phone', '').strip()
    amount = request.data.get('amount')

    if not phone or not amount:
        return Response({'error': 'Phone and amount required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        amount = round(float(amount), 2)
    except (ValueError, TypeError):
        return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

    if amount < 1:
        return Response({'error': 'Minimum transfer is GH₵1.00'}, status=status.HTTP_400_BAD_REQUEST)
    if amount > 500:
        return Response({'error': 'Maximum transfer is GH₵500.00'}, status=status.HTTP_400_BAD_REQUEST)

    normalized = normalize_phone(phone)
    if normalized == request.user.phone:
        return Response({'error': 'Cannot transfer to yourself'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        recipient = Player.objects.get(phone=normalized, is_active=True)
    except Player.DoesNotExist:
        return Response({'error': 'Recipient not found'}, status=status.HTTP_404_NOT_FOUND)

    from decimal import Decimal
    amount_dec = Decimal(str(amount))

    with db_transaction.atomic():
        sender_wallet = Wallet.objects.select_for_update().get(player=request.user)
        if sender_wallet.available_balance < amount_dec:
            return Response({'error': 'Insufficient balance'}, status=status.HTTP_400_BAD_REQUEST)

        recipient_wallet = Wallet.objects.select_for_update().get(player=recipient)
        ref = f'TRF-{uuid.uuid4().hex[:12].upper()}'

        # Debit sender
        sender_before = sender_wallet.balance
        sender_wallet.balance -= amount_dec
        sender_wallet.save(update_fields=['balance', 'updated_at'])
        WalletTransaction.objects.create(
            wallet=sender_wallet, amount=-amount_dec, tx_type='transfer_out',
            reference=f'{ref}-OUT', status='completed',
            balance_before=sender_before, balance_after=sender_wallet.balance,
            metadata={'type': 'transfer_out', 'to_phone': normalized, 'to_name': recipient.get_display_name()},
        )

        # Credit recipient
        recip_before = recipient_wallet.balance
        recipient_wallet.balance += amount_dec
        recipient_wallet.save(update_fields=['balance', 'updated_at'])
        WalletTransaction.objects.create(
            wallet=recipient_wallet, amount=amount_dec, tx_type='transfer_in',
            reference=f'{ref}-IN', status='completed',
            balance_before=recip_before, balance_after=recipient_wallet.balance,
            metadata={'type': 'transfer_in', 'from_phone': request.user.phone, 'from_name': request.user.get_display_name()},
        )

    return Response({
        'success': True,
        'message': f'Sent GH₵{amount:.2f} to {recipient.get_display_name()}',
        'reference': ref,
        'new_balance': str(sender_wallet.balance),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_summary(request):
    """
    Enhanced wallet summary: balance, locked, available, recent transactions, limits.
    Casino-style wallet dashboard data.
    """
    from wallet.models import Wallet, WalletTransaction
    from game.models import GameConfig

    try:
        wallet = Wallet.objects.select_related('currency').get(player=request.user)
    except Wallet.DoesNotExist:
        return Response({'error': 'Wallet not found'}, status=status.HTTP_404_NOT_FOUND)

    config = GameConfig.objects.filter(currency=wallet.currency, is_active=True).first()

    recent_txns = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')[:10]
    txn_list = [{
        'id': str(t.id),
        'type': t.tx_type,
        'amount': str(t.amount),
        'status': t.status,
        'reference': t.reference,
        'time': t.created_at.isoformat(),
        'meta': t.metadata,
    } for t in recent_txns]

    return Response({
        'balance': str(wallet.balance),
        'locked': str(wallet.locked_balance),
        'available': str(wallet.available_balance),
        'currency_code': wallet.currency.code,
        'currency_symbol': wallet.currency.symbol,
        'min_deposit': str(config.min_deposit) if config else '1.00',
        'min_stake': str(config.min_stake) if config else '1.00',
        'max_cashout': str(config.max_cashout) if config else '10000.00',
        'recent_transactions': txn_list,
    })


@csrf_exempt
def paystack_cancel(request):
    """Paystack cancel callback — proxy router redirects here when payment is cancelled/failed."""
    reference = request.GET.get('reference', '')
    error = request.GET.get('error', '')
    payment_status = request.GET.get('status', 'cancelled')
    logger.info(f'Paystack cancel callback: {reference} status={payment_status} error={error}')

    from payments.models import Deposit

    if reference:
        deposit = Deposit.objects.filter(paystack_reference=reference, status__in=('pending', 'processing')).first()
        if deposit:
            deposit.status = 'failed'
            deposit.failure_reason = error or payment_status
            deposit.save(update_fields=['status', 'failure_reason'])

    return JsonResponse({'status': 'cancelled', 'message': 'Payment was cancelled or failed.', 'reference': reference})


@csrf_exempt
@require_POST
def paystack_webhook(request):
    """Handle Paystack webhooks."""
    try:
        body = request.body
        signature = request.headers.get('X-Paystack-Signature', '')

        # Verify signature
        if settings.PAYSTACK_SECRET_KEY and signature:
            expected = hmac.new(
                settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
                body,
                hashlib.sha512
            ).hexdigest()
            if expected != signature:
                logger.warning('Paystack webhook signature mismatch')
                return JsonResponse({'error': 'Invalid signature'}, status=400)

        data = json.loads(body)
        logger.info(f'Paystack webhook: {data.get("event")}')

        success = process_paystack_webhook(data)
        return JsonResponse({'status': 'success' if success else 'failed'})
    except Exception as e:
        logger.error(f'Paystack webhook error: {e}')
        return JsonResponse({'error': 'Processing failed'}, status=500)
