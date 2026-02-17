"""
Payment API Views & Webhook Handlers
"""

import json
import hmac
import hashlib
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from payments.services import (
    initiate_mobile_money_deposit, initiate_card_deposit, initiate_withdrawal,
    process_orchard_callback, process_paystack_webhook, validate_mobile_number,
    detect_network,
)

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deposit_mobile_money(request):
    """Initiate mobile money deposit."""
    amount = request.data.get('amount')
    mobile_number = request.data.get('mobile_number')
    network = request.data.get('network')

    if not amount or not mobile_number:
        return Response({'error': 'Amount and mobile number required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

    if not validate_mobile_number(mobile_number):
        return Response({'error': 'Invalid mobile number'}, status=status.HTTP_400_BAD_REQUEST)

    success, result = initiate_mobile_money_deposit(request.user, amount, mobile_number, network)

    if success:
        return Response({
            'success': True,
            'message': 'Payment prompt sent to your phone',
            'reference': result.orchard_reference,
            'deposit_id': str(result.id),
        })
    return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def withdraw(request):
    """Initiate withdrawal to mobile money."""
    amount = request.data.get('amount')
    mobile_number = request.data.get('mobile_number')
    network = request.data.get('network')

    if not amount or not mobile_number:
        return Response({'error': 'Amount and mobile number required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

    if not validate_mobile_number(mobile_number):
        return Response({'error': 'Invalid mobile number'}, status=status.HTTP_400_BAD_REQUEST)

    # Check wallet balance
    from wallet.models import Wallet
    try:
        wallet = Wallet.objects.get(player=request.user)
    except Wallet.DoesNotExist:
        return Response({'error': 'Wallet not found'}, status=status.HTTP_400_BAD_REQUEST)

    if wallet.available_balance < amount:
        return Response({'error': 'Insufficient balance'}, status=status.HTTP_400_BAD_REQUEST)

    # Deduct from wallet first
    from django.db import transaction as db_transaction
    from wallet.models import WalletTransaction
    import uuid

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

    success, result = initiate_withdrawal(request.user, amount, mobile_number, network)

    if success:
        return Response({
            'success': True,
            'message': 'Withdrawal processing',
            'reference': result.payout_reference,
        })
    return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)


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
