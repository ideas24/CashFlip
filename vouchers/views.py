import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from vouchers.models import Voucher, VoucherBatch, generate_voucher_code
from wallet.models import Wallet, WalletTransaction


# ==================== PUBLIC API ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def redeem_voucher(request):
    """Redeem a voucher code and credit the user's wallet."""
    code = (request.data.get('code') or '').strip().upper()
    if not code:
        return Response({'error': 'Voucher code is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        voucher = Voucher.objects.get(code=code)
    except Voucher.DoesNotExist:
        return Response({'error': 'Invalid voucher code.'}, status=status.HTTP_404_NOT_FOUND)

    if voucher.status == 'redeemed':
        return Response({'error': 'This voucher has already been redeemed.'}, status=status.HTTP_400_BAD_REQUEST)
    if voucher.status == 'disabled':
        return Response({'error': 'This voucher has been disabled.'}, status=status.HTTP_400_BAD_REQUEST)
    if voucher.is_expired:
        voucher.status = 'expired'
        voucher.save(update_fields=['status'])
        return Response({'error': 'This voucher has expired.'}, status=status.HTTP_400_BAD_REQUEST)
    if not voucher.is_redeemable:
        return Response({'error': 'This voucher cannot be redeemed.'}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        # Re-fetch with lock inside transaction
        voucher = Voucher.objects.select_for_update().get(pk=voucher.pk)
        if voucher.status != 'active':
            return Response({'error': 'This voucher has already been redeemed.'}, status=status.HTTP_400_BAD_REQUEST)

        # Credit wallet
        wallet, _ = Wallet.objects.select_for_update().get_or_create(
            player=request.user,
            defaults={'currency_id': 1, 'balance': Decimal('0.00')}
        )
        balance_before = wallet.balance
        wallet.balance += voucher.amount
        wallet.save(update_fields=['balance', 'updated_at'])

        # Create wallet transaction
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=voucher.amount,
            tx_type='voucher',
            reference=f'VOUCHER-{voucher.code}-{uuid.uuid4().hex[:8]}',
            status='completed',
            balance_before=balance_before,
            balance_after=wallet.balance,
            metadata={'voucher_id': str(voucher.id), 'voucher_code': voucher.code},
        )

        # Mark voucher as redeemed
        voucher.status = 'redeemed'
        voucher.redeemed_by = request.user
        voucher.redeemed_at = timezone.now()
        voucher.save(update_fields=['status', 'redeemed_by', 'redeemed_at'])

    return Response({
        'success': True,
        'amount': str(voucher.amount),
        'currency_code': voucher.currency_code,
        'new_balance': str(wallet.balance),
        'message': f'{voucher.currency_code} {voucher.amount} credited to your wallet!',
    })


# ==================== ADMIN API ====================

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_voucher_list(request):
    """List vouchers with optional filters."""
    qs = Voucher.objects.select_related('batch', 'redeemed_by', 'created_by')
    # Filters
    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)
    batch_id = request.query_params.get('batch')
    if batch_id:
        qs = qs.filter(batch_id=batch_id)
    search = request.query_params.get('search', '').strip()
    if search:
        qs = qs.filter(Q(code__icontains=search) | Q(notes__icontains=search))

    page = int(request.query_params.get('page', 1))
    per_page = min(int(request.query_params.get('per_page', 50)), 200)
    total = qs.count()
    vouchers = qs[(page - 1) * per_page: page * per_page]

    return Response({
        'vouchers': [{
            'id': str(v.id),
            'code': v.code,
            'amount': str(v.amount),
            'currency_code': v.currency_code,
            'status': v.status,
            'batch_id': str(v.batch_id) if v.batch_id else None,
            'batch_name': v.batch.name if v.batch else None,
            'created_by': v.created_by.phone if v.created_by else None,
            'redeemed_by': v.redeemed_by.phone if v.redeemed_by else None,
            'redeemed_at': v.redeemed_at.isoformat() if v.redeemed_at else None,
            'expires_at': v.expires_at.isoformat() if v.expires_at else None,
            'created_at': v.created_at.isoformat(),
            'notes': v.notes,
        } for v in vouchers],
        'total': total,
        'page': page,
        'per_page': per_page,
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_voucher_create(request):
    """Create a single voucher."""
    amount = request.data.get('amount')
    if not amount or Decimal(str(amount)) <= 0:
        return Response({'error': 'Valid amount required.'}, status=status.HTTP_400_BAD_REQUEST)

    expires_at = request.data.get('expires_at')
    voucher = Voucher.objects.create(
        amount=Decimal(str(amount)),
        currency_code=request.data.get('currency_code', 'GHS'),
        created_by=request.user,
        expires_at=expires_at or None,
        notes=request.data.get('notes', ''),
    )
    return Response({
        'id': str(voucher.id),
        'code': voucher.code,
        'amount': str(voucher.amount),
        'currency_code': voucher.currency_code,
        'status': voucher.status,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_voucher_disable(request, voucher_id):
    """Disable an active voucher."""
    try:
        voucher = Voucher.objects.get(id=voucher_id)
    except Voucher.DoesNotExist:
        return Response({'error': 'Voucher not found.'}, status=status.HTTP_404_NOT_FOUND)
    if voucher.status != 'active':
        return Response({'error': f'Cannot disable a {voucher.status} voucher.'}, status=status.HTTP_400_BAD_REQUEST)
    voucher.status = 'disabled'
    voucher.save(update_fields=['status'])
    return Response({'success': True, 'status': 'disabled'})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_batch_list(request):
    """List voucher batches."""
    batches = VoucherBatch.objects.annotate(
        total_vouchers=Count('vouchers'),
        redeemed=Count('vouchers', filter=Q(vouchers__status='redeemed')),
        active=Count('vouchers', filter=Q(vouchers__status='active')),
    ).select_related('created_by').order_by('-created_at')

    return Response({
        'batches': [{
            'id': str(b.id),
            'name': b.name,
            'amount': str(b.amount),
            'currency_code': b.currency_code,
            'quantity': b.quantity,
            'total_vouchers': b.total_vouchers,
            'redeemed': b.redeemed,
            'active': b.active,
            'created_by': b.created_by.phone if b.created_by else None,
            'expires_at': b.expires_at.isoformat() if b.expires_at else None,
            'created_at': b.created_at.isoformat(),
            'notes': b.notes,
        } for b in batches],
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_batch_create(request):
    """Create a batch of vouchers."""
    name = request.data.get('name', '').strip()
    amount = request.data.get('amount')
    quantity = request.data.get('quantity')

    if not name:
        return Response({'error': 'Batch name required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not amount or Decimal(str(amount)) <= 0:
        return Response({'error': 'Valid amount required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not quantity or int(quantity) <= 0 or int(quantity) > 1000:
        return Response({'error': 'Quantity must be 1-1000.'}, status=status.HTTP_400_BAD_REQUEST)

    qty = int(quantity)
    amt = Decimal(str(amount))
    currency = request.data.get('currency_code', 'GHS')
    expires_at = request.data.get('expires_at') or None

    batch = VoucherBatch.objects.create(
        name=name,
        amount=amt,
        currency_code=currency,
        quantity=qty,
        created_by=request.user,
        expires_at=expires_at,
        notes=request.data.get('notes', ''),
    )

    # Generate vouchers in bulk
    vouchers = []
    used_codes = set()
    for _ in range(qty):
        code = generate_voucher_code()
        while code in used_codes or Voucher.objects.filter(code=code).exists():
            code = generate_voucher_code()
        used_codes.add(code)
        vouchers.append(Voucher(
            code=code,
            amount=amt,
            currency_code=currency,
            batch=batch,
            created_by=request.user,
            expires_at=expires_at,
        ))
    Voucher.objects.bulk_create(vouchers)

    return Response({
        'id': str(batch.id),
        'name': batch.name,
        'amount': str(batch.amount),
        'quantity': batch.quantity,
        'codes': [v.code for v in vouchers],
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_voucher_stats(request):
    """Voucher dashboard stats."""
    total = Voucher.objects.count()
    active = Voucher.objects.filter(status='active').count()
    redeemed = Voucher.objects.filter(status='redeemed').count()
    disabled = Voucher.objects.filter(status='disabled').count()
    expired = Voucher.objects.filter(status='expired').count()
    total_value = sum(Voucher.objects.filter(status='redeemed').values_list('amount', flat=True))

    return Response({
        'total': total,
        'active': active,
        'redeemed': redeemed,
        'disabled': disabled,
        'expired': expired,
        'total_redeemed_value': str(total_value),
    })
