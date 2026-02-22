import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate
from django.db.models import Sum, Count, Q, Avg, F
from django.db.models.functions import TruncDate
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.models import Player, AdminRole, StaffMember, AuthConfig, PlayerProfile, SMSProvider
from game.models import GameSession, FlipResult, Currency, GameConfig, SimulatedGameConfig, StakeTier
from wallet.models import Wallet, WalletTransaction
from payments.models import Deposit, Withdrawal

from dashboard.permissions import IsStaffAdmin, HasDashboardPermission
from dashboard.serializers import (
    AdminLoginSerializer, AdminUserSerializer, PlayerListSerializer,
    AuthSettingsSerializer, RoleSerializer, StaffSerializer,
)

logger = logging.getLogger(__name__)


def _generate_jwt(player):
    """Generate JWT token for admin login."""
    import jwt
    from datetime import datetime
    payload = {
        'user_id': str(player.id),
        'exp': datetime.utcnow() + timedelta(hours=12),
        'iat': datetime.utcnow(),
        'admin': True,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm='HS256')


# ==================== AUTH ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    ser = AdminLoginSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    phone = ser.validated_data['phone']
    password = ser.validated_data['password']

    user = authenticate(request, phone=phone, password=password)
    if not user:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    if not user.is_superuser and not hasattr(user, 'staff_profile'):
        return Response({'error': 'Not authorized for admin access'}, status=status.HTTP_403_FORBIDDEN)

    if hasattr(user, 'staff_profile') and not user.staff_profile.is_active:
        return Response({'error': 'Staff account disabled'}, status=status.HTTP_403_FORBIDDEN)

    token = _generate_jwt(user)
    return Response({
        'access_token': token,
        'user': AdminUserSerializer(user).data,
    })


@api_view(['GET'])
@permission_classes([IsStaffAdmin])
def admin_me(request):
    return Response(AdminUserSerializer(request.user).data)


# ==================== DASHBOARD ====================

@api_view(['GET'])
@permission_classes([IsStaffAdmin])
def dashboard_stats(request):
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    # Player stats
    total_players = Player.objects.filter(is_staff=False).count()
    active_today = GameSession.objects.filter(created_at__date=today).values('player').distinct().count()

    yesterday_players = Player.objects.filter(date_joined__date__lte=yesterday, is_staff=False).count()
    player_change = round(((total_players - yesterday_players) / max(yesterday_players, 1)) * 100, 1)

    # Session stats
    sessions_today = GameSession.objects.filter(created_at__date=today).count()

    # Revenue stats
    deposits_today = Deposit.objects.filter(
        created_at__date=today, status='completed'
    ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

    withdrawals_today = Withdrawal.objects.filter(
        created_at__date=today, status='completed'
    ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

    revenue_today = deposits_today - withdrawals_today

    yesterday_revenue = (
        (Deposit.objects.filter(created_at__date=yesterday, status='completed').aggregate(s=Sum('amount'))['s'] or Decimal('0'))
        - (Withdrawal.objects.filter(created_at__date=yesterday, status='completed').aggregate(s=Sum('amount'))['s'] or Decimal('0'))
    )
    revenue_change = round(((revenue_today - yesterday_revenue) / max(yesterday_revenue, Decimal('1'))) * 100, 1)

    # GGR today
    stakes_today = GameSession.objects.filter(created_at__date=today).aggregate(s=Sum('stake_amount'))['s'] or Decimal('0')
    payouts_today = GameSession.objects.filter(
        created_at__date=today, status__in=['cashed_out', 'completed']
    ).aggregate(s=Sum('cashout_balance'))['s'] or Decimal('0')
    ggr_today = stakes_today - payouts_today

    # Revenue chart (30 days)
    chart_start = today - timedelta(days=29)
    daily_deps = dict(
        Deposit.objects.filter(created_at__date__gte=chart_start, status='completed')
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum('amount'))
        .values_list('day', 'total')
    )
    daily_wdrs = dict(
        Withdrawal.objects.filter(created_at__date__gte=chart_start, status='completed')
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum('amount'))
        .values_list('day', 'total')
    )
    daily_active = dict(
        GameSession.objects.filter(created_at__date__gte=chart_start)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(cnt=Count('player', distinct=True))
        .values_list('day', 'cnt')
    )

    revenue_chart = []
    for i in range(30):
        d = chart_start + timedelta(days=i)
        dep = float(daily_deps.get(d, 0) or 0)
        wdr = float(daily_wdrs.get(d, 0) or 0)
        revenue_chart.append({
            'date': d.strftime('%b %d'),
            'revenue': round(dep - wdr, 2),
            'players': daily_active.get(d, 0),
        })

    # Recent sessions
    recent_sessions = []
    for s in GameSession.objects.select_related('player').order_by('-created_at')[:8]:
        result = 'in play'
        if s.status == 'cashed_out':
            result = 'won'
        elif s.status in ('lost', 'completed') and (s.cashout_balance or 0) == 0:
            result = 'lost'
        elif s.status == 'completed':
            result = 'won' if (s.cashout_balance or 0) > 0 else 'lost'
        recent_sessions.append({
            'id': str(s.id),
            'player_name': s.player.get_display_name(),
            'stake': str(s.stake_amount),
            'result': result,
            'created_at': s.created_at.isoformat(),
        })

    # Recent transactions
    recent_transactions = []
    for dep in Deposit.objects.select_related('player').order_by('-created_at')[:4]:
        recent_transactions.append({
            'id': str(dep.id),
            'player_name': dep.player.get_display_name(),
            'type': 'deposit',
            'amount': str(dep.amount),
            'status': dep.status,
            'created_at': dep.created_at.isoformat(),
        })
    for wdr in Withdrawal.objects.select_related('player').order_by('-created_at')[:4]:
        recent_transactions.append({
            'id': str(wdr.id),
            'player_name': wdr.player.get_display_name(),
            'type': 'withdrawal',
            'amount': str(wdr.amount),
            'status': wdr.status,
            'created_at': wdr.created_at.isoformat(),
        })
    recent_transactions.sort(key=lambda x: x['created_at'], reverse=True)

    return Response({
        'total_players': total_players,
        'active_today': active_today,
        'total_sessions_today': sessions_today,
        'total_revenue_today': str(revenue_today),
        'total_deposits_today': str(deposits_today),
        'total_withdrawals_today': str(withdrawals_today),
        'ggr_today': str(ggr_today),
        'player_change_pct': str(player_change),
        'revenue_change_pct': str(revenue_change),
        'revenue_chart': revenue_chart,
        'recent_sessions': recent_sessions,
        'recent_transactions': recent_transactions[:8],
    })


# ==================== PLAYERS ====================

@api_view(['GET'])
@permission_classes([IsStaffAdmin])
def player_list(request):
    qs = Player.objects.filter(is_staff=False, is_superuser=False).order_by('-date_joined')
    search = request.query_params.get('search', '')
    if search:
        qs = qs.filter(Q(phone__icontains=search) | Q(display_name__icontains=search))

    page = int(request.query_params.get('page', 1))
    per_page = 25
    total = qs.count()
    players = qs[(page - 1) * per_page:page * per_page]

    return Response({
        'results': PlayerListSerializer(players, many=True).data,
        'count': total,
        'next': f'?page={page + 1}' if page * per_page < total else None,
        'previous': f'?page={page - 1}' if page > 1 else None,
    })


@api_view(['GET', 'PATCH'])
@permission_classes([IsStaffAdmin])
def player_update(request, player_id):
    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        return Response({'error': 'Player not found'}, status=404)

    if request.method == 'PATCH':
        if 'is_active' in request.data:
            player.is_active = request.data['is_active']
            player.save(update_fields=['is_active'])
        return Response(PlayerListSerializer(player).data)

    # GET — detailed player view
    wallet = getattr(player, 'wallet', None)
    profile = getattr(player, 'profile', None)
    sessions = GameSession.objects.filter(player=player).order_by('-created_at')[:10]
    deposits = Deposit.objects.filter(player=player).order_by('-created_at')[:10]
    withdrawals = Withdrawal.objects.filter(player=player).order_by('-created_at')[:10]

    recent_sessions = [{
        'id': str(s.id), 'stake': str(s.stake_amount), 'payout': str(s.cashout_balance or 0),
        'status': s.status, 'flips': s.flip_count, 'created_at': s.created_at.isoformat(),
    } for s in sessions]

    recent_deposits = [{
        'id': str(d.id), 'amount': str(d.amount), 'status': d.status,
        'reference': d.orchard_reference or d.paystack_reference or '',
        'created_at': d.created_at.isoformat(),
    } for d in deposits]

    recent_withdrawals = [{
        'id': str(w.id), 'amount': str(w.amount), 'status': w.status,
        'reference': w.payout_reference or '', 'created_at': w.created_at.isoformat(),
    } for w in withdrawals]

    total_wagered = player.game_sessions.aggregate(s=Sum('stake_amount'))['s'] or 0
    total_won = player.game_sessions.filter(status='cashed_out').aggregate(s=Sum('cashout_balance'))['s'] or 0
    total_deposited = Deposit.objects.filter(player=player, status='completed').aggregate(s=Sum('amount'))['s'] or 0
    total_withdrawn = Withdrawal.objects.filter(player=player, status='completed').aggregate(s=Sum('amount'))['s'] or 0

    return Response({
        'id': str(player.id),
        'phone': player.phone or '',
        'display_name': player.get_display_name(),
        'is_active': player.is_active,
        'date_joined': player.date_joined.isoformat(),
        'last_login': player.last_login.isoformat() if player.last_login else None,
        'balance': str(wallet.balance) if wallet else '0.00',
        'total_sessions': player.game_sessions.count(),
        'total_wagered': str(total_wagered),
        'total_won': str(total_won),
        'total_deposited': str(total_deposited),
        'total_withdrawn': str(total_withdrawn),
        'recent_sessions': recent_sessions,
        'recent_deposits': recent_deposits,
        'recent_withdrawals': recent_withdrawals,
    })


# ==================== PLAYER WALLET CREDIT/DEBIT ====================

@api_view(['POST'])
@permission_classes([IsStaffAdmin])
def player_wallet_adjust(request, player_id):
    """Admin credit or debit a player's wallet. tx_type: 'admin_credit' or 'admin_debit'."""
    import uuid as _uuid
    from decimal import Decimal, InvalidOperation
    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        return Response({'error': 'Player not found'}, status=404)

    amount_raw = request.data.get('amount')
    tx_type = request.data.get('tx_type', 'admin_credit')
    note = request.data.get('note', '')

    if tx_type not in ('admin_credit', 'admin_debit'):
        return Response({'error': 'tx_type must be admin_credit or admin_debit'}, status=400)

    try:
        amount = Decimal(str(amount_raw))
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError, TypeError):
        return Response({'error': 'Invalid amount'}, status=400)

    wallet = getattr(player, 'wallet', None)
    if not wallet:
        return Response({'error': 'Player has no wallet'}, status=400)

    from django.db import transaction as db_tx
    with db_tx.atomic():
        wallet_obj = Wallet.objects.select_for_update().get(pk=wallet.pk)
        before = wallet_obj.balance
        if tx_type == 'admin_credit':
            wallet_obj.balance += amount
        else:
            if wallet_obj.balance < amount:
                return Response({'error': 'Insufficient balance for debit'}, status=400)
            wallet_obj.balance -= amount
        wallet_obj.save(update_fields=['balance', 'updated_at'])
        WalletTransaction.objects.create(
            wallet=wallet_obj,
            amount=amount if tx_type == 'admin_credit' else -amount,
            tx_type=tx_type,
            reference=f'ADMIN-{_uuid.uuid4().hex[:12].upper()}',
            status='completed',
            balance_before=before,
            balance_after=wallet_obj.balance,
            metadata={'note': note, 'admin': str(request.user.id)},
        )

    return Response({
        'success': True,
        'tx_type': tx_type,
        'amount': str(amount),
        'new_balance': str(wallet_obj.balance),
        'player_id': str(player.id),
    })


# ==================== SESSIONS ====================

@api_view(['GET'])
@permission_classes([IsStaffAdmin])
def session_list(request):
    qs = GameSession.objects.select_related('player', 'currency').order_by('-created_at')
    search = request.query_params.get('search', '')
    status_filter = request.query_params.get('status', '')
    if search:
        qs = qs.filter(Q(player__phone__icontains=search) | Q(player__display_name__icontains=search))
    if status_filter:
        qs = qs.filter(status=status_filter)

    page = int(request.query_params.get('page', 1))
    per_page = 25
    total = qs.count()
    sessions = qs[(page - 1) * per_page:page * per_page]

    results = []
    for s in sessions:
        flips = s.flips.count() if hasattr(s, 'flips') else 0
        result = ''
        if s.status == 'cashed_out':
            result = 'won'
        elif s.status in ('lost', 'completed') and (s.cashout_balance or 0) == 0:
            result = 'lost'
        elif s.status == 'active':
            result = 'in play'
        else:
            result = 'won' if (s.cashout_balance or 0) > 0 else 'lost'

        results.append({
            'id': str(s.id),
            'player_name': s.player.get_display_name(),
            'player_phone': s.player.phone or '',
            'stake': str(s.stake_amount),
            'currency': s.currency.code if s.currency else 'GHS',
            'flips': flips,
            'result': result,
            'payout': str(s.cashout_balance or 0),
            'created_at': s.created_at.isoformat(),
            'status': s.status,
        })

    return Response({
        'results': results,
        'count': total,
        'next': f'?page={page + 1}' if page * per_page < total else None,
    })


@api_view(['GET'])
@permission_classes([IsStaffAdmin])
def session_detail(request, session_id):
    try:
        s = GameSession.objects.select_related('player', 'currency').get(id=session_id)
    except GameSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=404)

    flips = FlipResult.objects.filter(session=s).order_by('flip_number')
    flip_list = [{
        'flip_number': f.flip_number,
        'value': str(f.value),
        'is_zero': f.is_zero,
        'cumulative_balance': str(f.cumulative_balance),
        'timestamp': f.timestamp.isoformat(),
    } for f in flips]

    result = ''
    if s.status == 'cashed_out':
        result = 'won'
    elif s.status in ('lost', 'completed') and (s.cashout_balance or 0) == 0:
        result = 'lost'
    elif s.status == 'active':
        result = 'in play'
    else:
        result = 'won' if (s.cashout_balance or 0) > 0 else 'lost'

    return Response({
        'id': str(s.id),
        'player_name': s.player.get_display_name(),
        'player_phone': s.player.phone or '',
        'player_id': str(s.player.id),
        'stake': str(s.stake_amount),
        'currency': s.currency.code if s.currency else 'GHS',
        'currency_symbol': s.currency.symbol if s.currency else 'GH₵',
        'flips': s.flip_count,
        'payout': str(s.cashout_balance or 0),
        'result': result,
        'status': s.status,
        'created_at': s.created_at.isoformat(),
        'ended_at': s.ended_at.isoformat() if s.ended_at else None,
        'server_seed_hash': s.server_seed_hash,
        'flip_history': flip_list,
    })


# ==================== TRANSACTIONS ====================

@api_view(['GET'])
@permission_classes([IsStaffAdmin])
def transaction_list(request):
    search = request.query_params.get('search', '')
    type_filter = request.query_params.get('type', '')
    page = int(request.query_params.get('page', 1))
    per_page = 25

    items = []

    # Deposits
    if type_filter in ('', 'deposit'):
        dep_qs = Deposit.objects.select_related('player').order_by('-created_at')
        if search:
            dep_qs = dep_qs.filter(
                Q(player__phone__icontains=search) |
                Q(orchard_reference__icontains=search) |
                Q(paystack_reference__icontains=search)
            )
        for d in dep_qs[:100]:
            items.append({
                'id': str(d.id),
                'player_name': d.player.get_display_name(),
                'player_phone': d.player.phone or '',
                'type': 'deposit',
                'amount': str(d.amount),
                'currency': d.currency_code or 'GHS',
                'status': d.status,
                'reference': d.orchard_reference or d.paystack_reference or '',
                'provider': d.method or 'mobile_money',
                'created_at': d.created_at.isoformat(),
            })

    # Withdrawals
    if type_filter in ('', 'withdrawal'):
        wdr_qs = Withdrawal.objects.select_related('player').order_by('-created_at')
        if search:
            wdr_qs = wdr_qs.filter(
                Q(player__phone__icontains=search) |
                Q(payout_reference__icontains=search)
            )
        for w in wdr_qs[:100]:
            items.append({
                'id': str(w.id),
                'player_name': w.player.get_display_name(),
                'player_phone': w.player.phone or '',
                'type': 'withdrawal',
                'amount': str(w.amount),
                'currency': w.currency_code or 'GHS',
                'status': w.status,
                'reference': w.payout_reference or '',
                'provider': 'mobile_money',
                'created_at': w.created_at.isoformat(),
            })

    items.sort(key=lambda x: x['created_at'], reverse=True)
    total = len(items)
    paged = items[(page - 1) * per_page:page * per_page]

    return Response({
        'results': paged,
        'count': total,
        'next': f'?page={page + 1}' if page * per_page < total else None,
    })


# ==================== FINANCE ====================

@api_view(['GET'])
@permission_classes([IsStaffAdmin])
def finance_overview(request):
    # Query params for sorting and filtering
    sort_by = request.query_params.get('sort', '-created_at')
    tx_filter = request.query_params.get('type', 'all')  # all, deposits, withdrawals
    period = request.query_params.get('period', '30d')
    days = {'7d': 7, '30d': 30, '90d': 90, 'all': 365}.get(period, 30)
    start_date = timezone.now().date() - timedelta(days=days - 1)

    # All-time totals
    total_deposits = Deposit.objects.filter(status='completed').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    total_withdrawals = Withdrawal.objects.filter(status='completed').aggregate(s=Sum('amount'))['s'] or Decimal('0')

    # Period totals
    period_deps = Deposit.objects.filter(status='completed', created_at__date__gte=start_date)
    period_wdrs_completed = Withdrawal.objects.filter(status='completed', created_at__date__gte=start_date)
    period_dep_total = period_deps.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    period_wdr_total = period_wdrs_completed.aggregate(s=Sum('amount'))['s'] or Decimal('0')

    # GGR for the period (stakes - payouts)
    period_sessions = GameSession.objects.filter(created_at__date__gte=start_date)
    total_stakes = period_sessions.aggregate(s=Sum('stake_amount'))['s'] or Decimal('0')
    total_payouts = period_sessions.filter(
        status__in=['cashed_out', 'completed']
    ).aggregate(s=Sum('cashout_balance'))['s'] or Decimal('0')
    ggr = total_stakes - total_payouts
    ggr_margin = round(float(ggr) / max(float(total_stakes), 1) * 100, 1)

    # Pending withdrawals
    pending_wdrs = Withdrawal.objects.filter(status='pending')
    pending_total = pending_wdrs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    pending_count = pending_wdrs.count()

    # Withdrawal pipeline (by status)
    from collections import Counter
    wdr_pipeline = dict(
        Withdrawal.objects.filter(created_at__date__gte=start_date)
        .values('status').annotate(cnt=Count('id'), total=Sum('amount'))
        .values_list('status', 'total')
    )

    valid_sort_fields = {'created_at', '-created_at', 'amount', '-amount', 'player__phone', '-player__phone'}
    if sort_by not in valid_sort_fields:
        sort_by = '-created_at'

    pending_list = []
    for w in pending_wdrs.select_related('player').order_by(sort_by)[:30]:
        pending_list.append({
            'id': str(w.id),
            'player_name': w.player.get_display_name(),
            'player_phone': w.player.phone,
            'type': 'withdrawal',
            'amount': str(w.amount),
            'status': w.status,
            'provider': getattr(w, 'provider', 'mobile_money'),
            'created_at': w.created_at.isoformat(),
        })

    # Recent transactions with filtering
    recent = []
    if tx_filter in ('all', 'deposits'):
        for d in Deposit.objects.select_related('player').filter(status='completed').order_by(sort_by)[:15]:
            recent.append({
                'id': str(d.id), 'player_name': d.player.get_display_name(),
                'player_phone': d.player.phone,
                'type': 'deposit', 'amount': str(d.amount), 'status': d.status,
                'provider': getattr(d, 'provider', 'mobile_money'),
                'created_at': d.created_at.isoformat(),
            })
    if tx_filter in ('all', 'withdrawals'):
        for w in Withdrawal.objects.select_related('player').filter(status='completed').order_by(sort_by)[:15]:
            recent.append({
                'id': str(w.id), 'player_name': w.player.get_display_name(),
                'player_phone': w.player.phone,
                'type': 'withdrawal', 'amount': str(w.amount), 'status': w.status,
                'provider': getattr(w, 'provider', 'mobile_money'),
                'created_at': w.created_at.isoformat(),
            })

    if sort_by in ('-amount', 'amount'):
        recent.sort(key=lambda x: float(x['amount']), reverse=sort_by.startswith('-'))
    else:
        recent.sort(key=lambda x: x['created_at'], reverse=sort_by.startswith('-'))

    # Daily P&L chart
    daily_deps = dict(
        period_deps.annotate(day=TruncDate('created_at'))
        .values('day').annotate(total=Sum('amount'))
        .values_list('day', 'total')
    )
    daily_wdrs = dict(
        period_wdrs_completed.annotate(day=TruncDate('created_at'))
        .values('day').annotate(total=Sum('amount'))
        .values_list('day', 'total')
    )
    daily_stakes_map = dict(
        period_sessions.annotate(day=TruncDate('created_at'))
        .values('day').annotate(total=Sum('stake_amount'))
        .values_list('day', 'total')
    )
    daily_payouts_map = dict(
        period_sessions.filter(status__in=['cashed_out', 'completed'])
        .annotate(day=TruncDate('created_at'))
        .values('day').annotate(total=Sum('cashout_balance'))
        .values_list('day', 'total')
    )
    daily_pnl = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        dep = float(daily_deps.get(d, 0) or 0)
        wdr = float(daily_wdrs.get(d, 0) or 0)
        stk = float(daily_stakes_map.get(d, 0) or 0)
        pay = float(daily_payouts_map.get(d, 0) or 0)
        daily_pnl.append({
            'date': d.strftime('%b %d'),
            'deposits': round(dep, 2),
            'withdrawals': round(wdr, 2),
            'ggr': round(stk - pay, 2),
            'net_flow': round(dep - wdr, 2),
        })

    return Response({
        'stats': {
            'total_deposits': str(total_deposits),
            'total_withdrawals': str(total_withdrawals),
            'net_revenue': str(total_deposits - total_withdrawals),
            'pending_withdrawals': str(pending_total),
            'pending_count': pending_count,
            'period_deposits': str(period_dep_total),
            'period_withdrawals': str(period_wdr_total),
            'ggr': str(ggr),
            'ggr_margin': str(ggr_margin),
            'total_stakes': str(total_stakes),
            'total_payouts': str(total_payouts),
        },
        'pending_withdrawals': pending_list,
        'recent': recent[:20],
        'daily_pnl': daily_pnl,
    })


@api_view(['POST'])
@permission_classes([IsStaffAdmin])
def approve_withdrawal(request, wdr_id):
    try:
        w = Withdrawal.objects.get(id=wdr_id, status='pending')
    except Withdrawal.DoesNotExist:
        return Response({'error': 'Withdrawal not found or already processed'}, status=404)
    w.status = 'completed'
    w.save(update_fields=['status'])
    return Response({'status': 'approved'})


@api_view(['POST'])
@permission_classes([IsStaffAdmin])
def reject_withdrawal(request, wdr_id):
    try:
        w = Withdrawal.objects.get(id=wdr_id, status='pending')
    except Withdrawal.DoesNotExist:
        return Response({'error': 'Withdrawal not found or already processed'}, status=404)
    w.status = 'rejected'
    w.save(update_fields=['status'])
    # Refund wallet
    try:
        wallet = w.player.wallet
        wallet.balance += w.amount
        wallet.save(update_fields=['balance'])
    except Exception:
        pass
    return Response({'status': 'rejected'})


# ==================== PARTNERS ====================

def _serialize_operator(op):
    """Serialize an Operator to dict."""
    try:
        from partner.models import OperatorSession
        sessions_count = OperatorSession.objects.filter(operator=op).count()
    except Exception:
        sessions_count = 0
    return {
        'id': str(op.id),
        'name': op.name,
        'slug': op.slug,
        'website': op.website or '',
        'contact_email': op.contact_email or '',
        'contact_phone': op.contact_phone or '',
        'status': op.status,
        'debit_url': op.debit_url or '',
        'credit_url': op.credit_url or '',
        'rollback_url': op.rollback_url or '',
        'commission_percent': str(op.commission_percent),
        'settlement_frequency': op.settlement_frequency,
        'min_settlement_amount': str(op.min_settlement_amount),
        'notes': op.notes or '',
        'total_sessions': sessions_count,
        'total_revenue': '0.00',
        'api_keys_count': op.api_keys.filter(is_active=True).count(),
        'created_at': op.created_at.isoformat(),
        'updated_at': op.updated_at.isoformat(),
    }


@api_view(['GET', 'POST'])
@permission_classes([IsStaffAdmin])
def partner_list(request):
    try:
        from partner.models import Operator
    except ImportError:
        return Response({'results': [], 'count': 0})

    if request.method == 'POST':
        data = request.data
        name = data.get('name', '').strip()
        slug = data.get('slug', '').strip()
        if not name or not slug:
            return Response({'error': 'Name and slug are required'}, status=400)
        if Operator.objects.filter(slug=slug).exists():
            return Response({'error': f'Slug "{slug}" already exists'}, status=400)
        op = Operator.objects.create(
            name=name,
            slug=slug,
            website=data.get('website', ''),
            contact_email=data.get('contact_email', ''),
            contact_phone=data.get('contact_phone', ''),
            status=data.get('status', 'pending'),
            commission_percent=data.get('commission_percent', 20),
            settlement_frequency=data.get('settlement_frequency', 'weekly'),
            min_settlement_amount=data.get('min_settlement_amount', 100),
            notes=data.get('notes', ''),
        )
        return Response(_serialize_operator(op), status=201)

    operators = Operator.objects.all().order_by('-created_at')
    results = [_serialize_operator(op) for op in operators]
    return Response({
        'results': results,
        'count': len(results),
        'status_choices': [
            {'value': 'pending', 'label': 'Pending Approval'},
            {'value': 'active', 'label': 'Active'},
            {'value': 'suspended', 'label': 'Suspended'},
            {'value': 'deactivated', 'label': 'Deactivated'},
        ],
        'settlement_choices': [
            {'value': 'daily', 'label': 'Daily'},
            {'value': 'weekly', 'label': 'Weekly'},
            {'value': 'monthly', 'label': 'Monthly'},
        ],
    })


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsStaffAdmin])
def partner_detail(request, partner_id):
    try:
        from partner.models import Operator
        op = Operator.objects.get(pk=partner_id)
    except ImportError:
        return Response({'error': 'Partner module not installed'}, status=500)
    except Operator.DoesNotExist:
        return Response({'error': 'Partner not found'}, status=404)

    if request.method == 'DELETE':
        op.delete()
        return Response(status=204)

    if request.method == 'PATCH':
        data = request.data
        updatable = [
            'name', 'slug', 'website', 'contact_email', 'contact_phone',
            'status', 'debit_url', 'credit_url', 'rollback_url',
            'commission_percent', 'settlement_frequency', 'min_settlement_amount', 'notes',
        ]
        updated = []
        for field in updatable:
            if field in data:
                setattr(op, field, data[field])
                updated.append(field)
        if updated:
            op.save(update_fields=updated + ['updated_at'])
        return Response(_serialize_operator(op))

    return Response(_serialize_operator(op))


@api_view(['GET', 'POST'])
@permission_classes([IsStaffAdmin])
def partner_api_keys(request, partner_id):
    """List, create, or revoke API keys for a partner."""
    try:
        from partner.models import Operator, OperatorAPIKey
        op = Operator.objects.get(pk=partner_id)
    except ImportError:
        return Response({'error': 'Partner module not installed'}, status=500)
    except Operator.DoesNotExist:
        return Response({'error': 'Partner not found'}, status=404)

    if request.method == 'POST':
        import secrets as _secrets
        label = request.data.get('label', 'Default').strip() or 'Default'
        api_key = f'cf_live_{_secrets.token_hex(20)}'
        api_secret = _secrets.token_hex(32)
        key_obj = OperatorAPIKey.objects.create(
            operator=op,
            label=label,
            api_key=api_key,
            api_secret=api_secret,
            is_active=True,
            rate_limit_per_minute=request.data.get('rate_limit_per_minute', 120),
        )
        # Return full secret only on creation
        return Response({
            'id': str(key_obj.id),
            'label': key_obj.label,
            'api_key': key_obj.api_key,
            'api_secret': key_obj.api_secret,
            'is_active': key_obj.is_active,
            'rate_limit_per_minute': key_obj.rate_limit_per_minute,
            'ip_whitelist': key_obj.ip_whitelist,
            'created_at': key_obj.created_at.isoformat(),
            'last_used_at': None,
            'just_created': True,
        }, status=201)

    keys = op.api_keys.all().order_by('-created_at')
    result = []
    for k in keys:
        result.append({
            'id': str(k.id),
            'label': k.label,
            'api_key': k.api_key,
            'api_secret_hint': k.api_secret[:8] + '...' + k.api_secret[-4:] if len(k.api_secret) > 12 else '***',
            'api_secret': k.api_secret,
            'is_active': k.is_active,
            'rate_limit_per_minute': k.rate_limit_per_minute,
            'ip_whitelist': k.ip_whitelist,
            'created_at': k.created_at.isoformat(),
            'last_used_at': k.last_used_at.isoformat() if k.last_used_at else None,
            'revoked_at': k.revoked_at.isoformat() if k.revoked_at else None,
        })
    return Response({'keys': result, 'count': len(result)})


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsStaffAdmin])
def partner_api_key_detail(request, partner_id, key_id):
    """Toggle or delete a specific API key."""
    try:
        from partner.models import OperatorAPIKey
        key_obj = OperatorAPIKey.objects.get(pk=key_id, operator_id=partner_id)
    except ImportError:
        return Response({'error': 'Partner module not installed'}, status=500)
    except OperatorAPIKey.DoesNotExist:
        return Response({'error': 'API key not found'}, status=404)

    if request.method == 'DELETE':
        key_obj.delete()
        return Response(status=204)

    # PATCH — toggle active, update label, rate limit, ip whitelist
    data = request.data
    if 'is_active' in data:
        key_obj.is_active = data['is_active']
        if not data['is_active']:
            from django.utils import timezone as tz
            key_obj.revoked_at = tz.now()
        else:
            key_obj.revoked_at = None
    if 'label' in data:
        key_obj.label = data['label']
    if 'rate_limit_per_minute' in data:
        key_obj.rate_limit_per_minute = data['rate_limit_per_minute']
    if 'ip_whitelist' in data:
        key_obj.ip_whitelist = data['ip_whitelist']
    key_obj.save()
    return Response({
        'id': str(key_obj.id),
        'label': key_obj.label,
        'api_key': key_obj.api_key,
        'api_secret_hint': key_obj.api_secret[:8] + '...' + key_obj.api_secret[-4:] if len(key_obj.api_secret) > 12 else '***',
        'api_secret': key_obj.api_secret,
        'is_active': key_obj.is_active,
        'rate_limit_per_minute': key_obj.rate_limit_per_minute,
        'ip_whitelist': key_obj.ip_whitelist,
        'created_at': key_obj.created_at.isoformat(),
        'last_used_at': key_obj.last_used_at.isoformat() if key_obj.last_used_at else None,
        'revoked_at': key_obj.revoked_at.isoformat() if key_obj.revoked_at else None,
    })


# ==================== ANALYTICS ====================

@api_view(['GET'])
@permission_classes([IsStaffAdmin])
def analytics_overview(request):
    period = request.query_params.get('period', '30d')
    days = {'7d': 7, '30d': 30, '90d': 90}.get(period, 30)
    start_date = timezone.now().date() - timedelta(days=days - 1)

    sessions = GameSession.objects.filter(created_at__date__gte=start_date)

    total_stakes = sessions.aggregate(s=Sum('stake_amount'))['s'] or Decimal('0')
    total_payouts = sessions.filter(
        status__in=['cashed_out', 'completed']
    ).aggregate(s=Sum('cashout_balance'))['s'] or Decimal('0')
    total_ggr = total_stakes - total_payouts

    avg_session = sessions.aggregate(a=Avg('stake_amount'))['a'] or Decimal('0')
    avg_flips = 0
    session_count = sessions.count()
    if session_count > 0:
        total_flips = FlipResult.objects.filter(session__in=sessions).count()
        avg_flips = total_flips / session_count

    # Retention: players from 7+ days ago who played again in last 7 days
    week_ago = timezone.now().date() - timedelta(days=7)
    old_players = Player.objects.filter(date_joined__date__lt=week_ago, is_staff=False).count()
    returned = GameSession.objects.filter(
        created_at__date__gte=week_ago,
        player__date_joined__date__lt=week_ago
    ).values('player').distinct().count()
    retention = round((returned / max(old_players, 1)) * 100, 1)

    # Daily revenue chart
    daily_stakes = dict(
        sessions.annotate(day=TruncDate('created_at'))
        .values('day').annotate(total=Sum('stake_amount'))
        .values_list('day', 'total')
    )
    daily_payouts = dict(
        sessions.filter(status__in=['cashed_out', 'completed'])
        .annotate(day=TruncDate('created_at'))
        .values('day').annotate(total=Sum('cashout_balance'))
        .values_list('day', 'total')
    )
    daily_new = dict(
        Player.objects.filter(date_joined__date__gte=start_date, is_staff=False)
        .annotate(day=TruncDate('date_joined'))
        .values('day').annotate(cnt=Count('id'))
        .values_list('day', 'cnt')
    )
    daily_active = dict(
        sessions.annotate(day=TruncDate('created_at'))
        .values('day').annotate(cnt=Count('player', distinct=True))
        .values_list('day', 'cnt')
    )

    revenue_chart = []
    player_chart = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        s = float(daily_stakes.get(d, 0) or 0)
        p = float(daily_payouts.get(d, 0) or 0)
        label = d.strftime('%b %d')
        revenue_chart.append({'date': label, 'revenue': round(s, 2), 'ggr': round(s - p, 2)})
        player_chart.append({
            'date': label,
            'new_players': daily_new.get(d, 0),
            'active_players': daily_active.get(d, 0),
        })

    # Win rate
    won_sessions = sessions.filter(status='cashed_out').count()
    lost_sessions = sessions.filter(status='lost').count()
    win_rate = round(won_sessions / max(won_sessions + lost_sessions, 1) * 100, 1)

    # Top players by GGR contribution (stake - payout)
    from django.db.models import F
    top_players = (
        sessions.values('player__phone')
        .annotate(
            total_staked=Sum('stake_amount'),
            total_won=Sum('cashout_balance'),
            games=Count('id'),
        )
        .order_by('-total_staked')[:10]
    )
    top_players_list = [{
        'player': p['player__phone'],
        'staked': str(p['total_staked'] or 0),
        'won': str(p['total_won'] or 0),
        'ggr': str((p['total_staked'] or 0) - (p['total_won'] or 0)),
        'games': p['games'],
    } for p in top_players]

    # Deposit / withdrawal volumes for the period
    period_deposits = Deposit.objects.filter(status='completed', created_at__date__gte=start_date)
    period_withdrawals = Withdrawal.objects.filter(status='completed', created_at__date__gte=start_date)
    total_dep_volume = period_deposits.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    total_wdr_volume = period_withdrawals.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    dep_count = period_deposits.count()
    wdr_count = period_withdrawals.count()

    # Daily deposits chart
    daily_deps = dict(
        period_deposits.annotate(day=TruncDate('created_at'))
        .values('day').annotate(total=Sum('amount'))
        .values_list('day', 'total')
    )
    daily_wdrs = dict(
        period_withdrawals.annotate(day=TruncDate('created_at'))
        .values('day').annotate(total=Sum('amount'))
        .values_list('day', 'total')
    )
    finance_chart = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        dep = float(daily_deps.get(d, 0) or 0)
        wdr = float(daily_wdrs.get(d, 0) or 0)
        finance_chart.append({'date': d.strftime('%b %d'), 'deposits': round(dep, 2), 'withdrawals': round(wdr, 2)})

    # Top denominations
    top_denoms = (
        FlipResult.objects.filter(session__in=sessions, is_zero=False)
        .values('value')
        .annotate(count=Count('id'))
        .order_by('-count')[:8]
    )
    top_denom_list = [{'value': str(d['value']), 'count': d['count']} for d in top_denoms]

    return Response({
        'summary': {
            'total_ggr': str(total_ggr),
            'total_stakes': str(total_stakes),
            'total_payouts': str(total_payouts),
            'avg_session_value': str(round(avg_session, 2)),
            'avg_flips_per_session': round(avg_flips, 1),
            'total_sessions': session_count,
            'won_sessions': won_sessions,
            'lost_sessions': lost_sessions,
            'win_rate': str(win_rate),
            'house_edge_actual': str(round(float(total_ggr) / max(float(total_stakes), 1) * 100, 1)),
            'retention_7d': str(retention),
            'deposit_volume': str(total_dep_volume),
            'withdrawal_volume': str(total_wdr_volume),
            'deposit_count': dep_count,
            'withdrawal_count': wdr_count,
        },
        'daily_revenue': revenue_chart,
        'daily_players': player_chart,
        'daily_finance': finance_chart,
        'top_players': top_players_list,
        'top_denominations': top_denom_list,
    })


# ==================== ROLES ====================

@api_view(['GET'])
@permission_classes([IsStaffAdmin])
def roles_list(request):
    roles = AdminRole.objects.all()
    staff = StaffMember.objects.select_related('player', 'role').filter(is_active=True)

    all_permissions = []
    groups = {
        'Players': ['view_players', 'manage_players'],
        'Game': ['view_sessions', 'manage_game_config'],
        'Finance': ['view_finance', 'view_transactions', 'approve_withdrawals'],
        'Partners': ['view_partners', 'manage_partners'],
        'Analytics': ['view_analytics'],
        'Settings': ['manage_settings', 'manage_roles', 'manage_staff', 'manage_ads', 'manage_referrals'],
    }
    for group, perms in groups.items():
        for p in perms:
            all_permissions.append({'key': p, 'label': p.replace('_', ' ').title(), 'group': group})

    return Response({
        'roles': RoleSerializer(roles, many=True).data,
        'staff': StaffSerializer(staff, many=True).data,
        'all_permissions': all_permissions,
    })


@api_view(['PATCH'])
@permission_classes([IsStaffAdmin])
def role_update(request, role_id):
    try:
        role = AdminRole.objects.get(id=role_id)
    except AdminRole.DoesNotExist:
        return Response({'error': 'Role not found'}, status=404)
    if 'permissions' in request.data:
        role.permissions = request.data['permissions']
        role.save(update_fields=['permissions'])
    return Response(RoleSerializer(role).data)


@api_view(['PATCH'])
@permission_classes([IsStaffAdmin])
def staff_update(request, user_id):
    try:
        sm = StaffMember.objects.get(player_id=user_id)
    except StaffMember.DoesNotExist:
        return Response({'error': 'Staff member not found'}, status=404)
    if 'role' in request.data:
        try:
            role = AdminRole.objects.get(codename=request.data['role'])
            sm.role = role
            sm.save(update_fields=['role'])
        except AdminRole.DoesNotExist:
            return Response({'error': 'Role not found'}, status=404)
    return Response({'status': 'updated'})


# ==================== SETTINGS ====================

@api_view(['GET', 'POST'])
@permission_classes([IsStaffAdmin])
def settings_view(request):
    auth_config = AuthConfig.get_config()

    # Get actual GameConfig (first active one, or defaults)
    game_config = GameConfig.objects.filter(is_active=True).first()
    sim_config = SimulatedGameConfig.get_active_config()
    all_sim_configs = SimulatedGameConfig.objects.all().order_by('-is_enabled', '-updated_at')

    if request.method == 'GET':
        game_data = {}
        if game_config:
            game_data = {
                'id': game_config.id,
                'currency': game_config.currency.code if game_config.currency else 'GHS',
                'house_edge_percent': str(game_config.house_edge_percent),
                'min_deposit': str(game_config.min_deposit),
                'max_cashout': str(game_config.max_cashout),
                'min_stake': str(game_config.min_stake),
                'pause_cost_percent': str(game_config.pause_cost_percent),
                'zero_base_rate': str(game_config.zero_base_rate),
                'zero_growth_rate': str(game_config.zero_growth_rate),
                'min_flips_before_zero': game_config.min_flips_before_zero,
                'min_flips_before_cashout': game_config.min_flips_before_cashout,
                'instant_cashout_enabled': game_config.instant_cashout_enabled,
                'instant_cashout_min_amount': str(game_config.instant_cashout_min_amount),
                'max_session_duration_minutes': game_config.max_session_duration_minutes,
                'auto_flip_seconds': game_config.auto_flip_seconds,
                'flip_animation_mode': game_config.flip_animation_mode,
                'flip_sprite_url': game_config.flip_sprite_url,
                'flip_sprite_frames': game_config.flip_sprite_frames,
                'flip_sprite_fps': game_config.flip_sprite_fps,
                'flip_display_mode': game_config.flip_display_mode,
                'flip_animation_speed_ms': game_config.flip_animation_speed_ms,
                'flip_sound_enabled': game_config.flip_sound_enabled,
                'flip_sound_url': game_config.flip_sound_url or '',
                'win_sound_url': game_config.win_sound_url or '',
                'cashout_sound_url': game_config.cashout_sound_url or '',
                'start_flip_image_url': game_config.start_flip_image_url or '',
                'simulated_feed_enabled': game_config.simulated_feed_enabled,
                'simulated_feed_data': game_config.simulated_feed_data or [],
                'is_active': game_config.is_active,
                'payout_mode': game_config.payout_mode,
                'normal_payout_target': str(game_config.normal_payout_target),
                'boost_payout_target': str(game_config.boost_payout_target),
                'boost_multiplier_factor': str(game_config.boost_multiplier_factor),
                'decay_factor': str(game_config.decay_factor),
                'max_flips_per_session': game_config.max_flips_per_session,
                'holiday_mode_enabled': game_config.holiday_mode_enabled,
                'holiday_boost_pct': str(game_config.holiday_boost_pct),
                'holiday_frequency': game_config.holiday_frequency,
                'holiday_max_tier_name': game_config.holiday_max_tier_name,
            }
        else:
            game_data = {
                'id': None,
                'currency': 'GHS',
                'house_edge_percent': '60.00',
                'min_deposit': '1.00',
                'max_cashout': '10000.00',
                'min_stake': '1.00',
                'pause_cost_percent': '10.00',
                'zero_base_rate': '0.0500',
                'zero_growth_rate': '0.0800',
                'min_flips_before_zero': 2,
                'min_flips_before_cashout': 3,
                'instant_cashout_enabled': True,
                'instant_cashout_min_amount': '5.00',
                'max_session_duration_minutes': 120,
                'auto_flip_seconds': 8,
                'flip_animation_mode': 'css3d',
                'flip_display_mode': 'face_then_gif',
                'flip_animation_speed_ms': 1500,
                'flip_sound_enabled': True,
                'flip_sound_url': '',
                'win_sound_url': '',
                'cashout_sound_url': '',
                'start_flip_image_url': '',
                'simulated_feed_enabled': False,
                'simulated_feed_data': [],
                'is_active': True,
                'payout_mode': 'normal',
                'normal_payout_target': '30.00',
                'boost_payout_target': '40.00',
                'boost_multiplier_factor': '1.33',
                'decay_factor': '0.0500',
                'max_flips_per_session': 10,
                'holiday_mode_enabled': False,
                'holiday_boost_pct': '70.00',
                'holiday_frequency': 1000,
                'holiday_max_tier_name': 'Standard',
            }

        sim_list = []
        for sc in all_sim_configs:
            sim_list.append({
                'id': sc.id,
                'name': sc.name,
                'is_enabled': sc.is_enabled,
                'outcome_mode': sc.outcome_mode,
                'outcome_mode_display': sc.get_outcome_mode_display(),
                'force_zero_at_flip': sc.force_zero_at_flip,
                'fixed_zero_probability': str(sc.fixed_zero_probability),
                'win_streak_length': sc.win_streak_length,
                'force_denomination_value': str(sc.force_denomination_value) if sc.force_denomination_value else '',
                'apply_to_all_players': sc.apply_to_all_players,
                'override_min_stake': str(sc.override_min_stake) if sc.override_min_stake else '',
                'override_max_cashout': str(sc.override_max_cashout) if sc.override_max_cashout else '',
                'grant_test_balance': str(sc.grant_test_balance),
                'auto_disable_after': sc.auto_disable_after,
                'sessions_used': sc.sessions_used,
                'notes': sc.notes,
                'updated_at': sc.updated_at.isoformat(),
            })

        # Feature config
        from game.models import FeatureConfig, DailyBonusConfig
        fc = FeatureConfig.get_config()
        feature_data = {
            'badges_enabled': fc.badges_enabled,
            'daily_wheel_enabled': fc.daily_wheel_enabled,
            'sounds_enabled': fc.sounds_enabled,
            'haptics_enabled': fc.haptics_enabled,
            'social_proof_enabled': fc.social_proof_enabled,
            'streak_badge_enabled': fc.streak_badge_enabled,
            'confetti_enabled': fc.confetti_enabled,
            'deposit_sound_enabled': fc.deposit_sound_enabled,
            'social_proof_min_amount': str(fc.social_proof_min_amount),
        }

        # Daily wheel config
        wc = DailyBonusConfig.get_config()
        wheel_data = {
            'is_enabled': wc.is_enabled if wc else True,
            'segments': wc.segments if wc else [],
            'cooldown_hours': wc.cooldown_hours if wc else 24,
            'max_spins_per_day': wc.max_spins_per_day if wc else 1,
            'require_deposit': wc.require_deposit if wc else False,
        }

        # Denominations for this currency
        from game.models import CurrencyDenomination
        denoms = []
        if game_config and game_config.currency:
            for d in CurrencyDenomination.objects.filter(currency=game_config.currency).order_by('display_order', 'value'):
                denoms.append({
                    'id': d.id,
                    'value': str(d.value),
                    'payout_multiplier': str(d.payout_multiplier),
                    'face_image_path': d.face_image_path,
                    'flip_sequence_prefix': d.flip_sequence_prefix,
                    'flip_sequence_frames': d.flip_sequence_frames,
                    'flip_gif_path': d.flip_gif_path,
                    'flip_video_path': d.flip_video_path,
                    'flip_sprite_path': d.flip_sprite_path,
                    'display_order': d.display_order,
                    'is_zero': d.is_zero,
                    'is_active': d.is_active,
                    'weight': d.weight,
                    'boost_payout_multiplier': str(d.boost_payout_multiplier),
                })

        # Branding
        from game.models import SiteBranding
        branding = SiteBranding.get_branding()
        branding_data = {
            'logo_url': branding.logo_cloud_url or (branding.logo.url if branding.logo else ''),
            'logo_icon_url': branding.logo_icon_cloud_url or (branding.logo_icon.url if branding.logo_icon else ''),
            'loading_animation_url': branding.loading_animation_cloud_url or (branding.loading_animation.url if branding.loading_animation else ''),
            'primary_color': branding.primary_color,
            'secondary_color': branding.secondary_color,
            'accent_color': branding.accent_color,
            'background_color': branding.background_color,
            'tagline': branding.tagline,
            'regulatory_logo_url': branding.regulatory_logo_cloud_url or (branding.regulatory_logo.url if branding.regulatory_logo else ''),
            'regulatory_text': branding.regulatory_text,
            'age_restriction_text': branding.age_restriction_text,
            'responsible_gaming_text': branding.responsible_gaming_text,
            'show_regulatory_footer': branding.show_regulatory_footer,
        }

        # Stake tiers
        tiers_data = []
        if game_config and game_config.currency:
            for t in StakeTier.objects.filter(currency=game_config.currency).order_by('display_order', 'min_stake'):
                tiers_data.append({
                    'id': t.id,
                    'name': t.name,
                    'min_stake': str(t.min_stake),
                    'max_stake': str(t.max_stake),
                    'denomination_ids': list(t.denominations.values_list('id', flat=True)),
                    'display_order': t.display_order,
                    'is_active': t.is_active,
                })

        # Legal documents
        from game.models import LegalDocument
        legal = LegalDocument.get_legal()
        legal_data = {
            'privacy_policy': legal.privacy_policy,
            'terms_of_service': legal.terms_of_service,
            'sms_disclosure': legal.sms_disclosure,
            'support_email': legal.support_email,
            'support_phone': legal.support_phone,
            'company_name': legal.company_name,
            'company_address': legal.company_address,
            'license_info': legal.license_info,
        }

        return Response({
            'auth': AuthSettingsSerializer(auth_config).data,
            'game': game_data,
            'features': feature_data,
            'wheel': wheel_data,
            'denominations': denoms,
            'stake_tiers': tiers_data,
            'branding': branding_data,
            'legal': legal_data,
            'simulated_configs': sim_list,
            'outcome_mode_choices': [
                {'value': c[0], 'label': c[1]} for c in SimulatedGameConfig.OUTCOME_CHOICES
            ],
        })

    # POST — save settings
    auth_data = request.data.get('auth', {})
    if auth_data:
        for field in ['sms_otp_enabled', 'whatsapp_otp_enabled', 'email_password_enabled',
                      'google_enabled', 'facebook_enabled', 'otp_expiry_minutes', 'max_otp_per_hour']:
            if field in auth_data:
                setattr(auth_config, field, auth_data[field])
        auth_config.save()

    game_data = request.data.get('game', {})
    if game_data and game_config:
        game_fields = ['house_edge_percent', 'min_deposit', 'max_cashout', 'min_stake',
                       'pause_cost_percent', 'zero_base_rate', 'zero_growth_rate',
                       'min_flips_before_zero', 'min_flips_before_cashout',
                       'instant_cashout_enabled', 'instant_cashout_min_amount',
                       'max_session_duration_minutes',
                       'auto_flip_seconds', 'flip_animation_mode', 'flip_sprite_url', 'flip_sprite_frames', 'flip_sprite_fps', 'flip_display_mode', 'flip_animation_speed_ms',
                       'flip_sound_enabled', 'flip_sound_url', 'win_sound_url', 'cashout_sound_url',
                       'start_flip_image_url', 'simulated_feed_enabled', 'simulated_feed_data',
                       'payout_mode', 'normal_payout_target', 'boost_payout_target', 'boost_multiplier_factor',
                       'decay_factor', 'max_flips_per_session',
                       'holiday_mode_enabled', 'holiday_boost_pct', 'holiday_frequency', 'holiday_max_tier_name']
        updated = []
        for field in game_fields:
            if field in game_data:
                setattr(game_config, field, game_data[field])
                updated.append(field)
        if updated:
            game_config.save(update_fields=updated + ['updated_at'])

    # Save feature config
    from game.models import FeatureConfig, DailyBonusConfig
    feat_data = request.data.get('features', {})
    if feat_data:
        fc = FeatureConfig.get_config()
        feat_fields = ['badges_enabled', 'daily_wheel_enabled', 'sounds_enabled',
                       'haptics_enabled', 'social_proof_enabled', 'streak_badge_enabled',
                       'confetti_enabled', 'deposit_sound_enabled', 'social_proof_min_amount']
        updated = []
        for field in feat_fields:
            if field in feat_data:
                setattr(fc, field, feat_data[field])
                updated.append(field)
        if updated:
            fc.save(update_fields=updated + ['updated_at'])

    # Save daily wheel config
    wheel_data = request.data.get('wheel', {})
    if wheel_data:
        wc = DailyBonusConfig.get_config()
        if not wc:
            wc = DailyBonusConfig(pk=1)
        wheel_fields = ['is_enabled', 'segments', 'cooldown_hours', 'max_spins_per_day', 'require_deposit']
        updated = []
        for field in wheel_fields:
            if field in wheel_data:
                setattr(wc, field, wheel_data[field])
                updated.append(field)
        if updated:
            wc.save(update_fields=updated + ['updated_at'])

    # Save denominations
    from game.models import CurrencyDenomination
    denoms_data = request.data.get('denominations', [])
    if denoms_data and game_config and game_config.currency:
        from decimal import Decimal
        existing_ids = set()
        for dd in denoms_data:
            denom_id = dd.get('id')
            if denom_id:
                try:
                    d = CurrencyDenomination.objects.get(id=denom_id, currency=game_config.currency)
                except CurrencyDenomination.DoesNotExist:
                    continue
            else:
                d = CurrencyDenomination(currency=game_config.currency)

            d.value = Decimal(str(dd.get('value', 0)))
            d.payout_multiplier = Decimal(str(dd.get('payout_multiplier', 10)))
            d.face_image_path = dd.get('face_image_path', '')
            d.flip_sequence_prefix = dd.get('flip_sequence_prefix', '')
            d.flip_sequence_frames = dd.get('flip_sequence_frames', 31)
            d.flip_gif_path = dd.get('flip_gif_path', '')
            d.flip_video_path = dd.get('flip_video_path', '')
            d.flip_sprite_path = dd.get('flip_sprite_path', '')
            d.display_order = dd.get('display_order', 0)
            d.is_zero = dd.get('is_zero', False)
            d.is_active = dd.get('is_active', True)
            d.weight = dd.get('weight', 10)
            d.boost_payout_multiplier = Decimal(str(dd.get('boost_payout_multiplier', 0)))
            d.save()
            existing_ids.add(d.id)

        # Delete denominations that were removed from the list
        if existing_ids:
            CurrencyDenomination.objects.filter(
                currency=game_config.currency
            ).exclude(id__in=existing_ids).delete()

    # Save branding (text fields + Cloudinary URL overrides)
    from game.models import SiteBranding
    branding_data = request.data.get('branding', {})
    if branding_data:
        branding = SiteBranding.get_branding()
        branding_fields = ['primary_color', 'secondary_color', 'accent_color',
                           'background_color', 'tagline', 'regulatory_text',
                           'age_restriction_text', 'responsible_gaming_text',
                           'show_regulatory_footer',
                           'logo_cloud_url', 'logo_icon_cloud_url',
                           'loading_animation_cloud_url', 'regulatory_logo_cloud_url']
        # Map frontend field names → model field names for Cloudinary URLs
        url_field_map = {
            'logo_url': 'logo_cloud_url',
            'logo_icon_url': 'logo_icon_cloud_url',
            'loading_animation_url': 'loading_animation_cloud_url',
            'regulatory_logo_url': 'regulatory_logo_cloud_url',
        }
        updated = []
        for field in branding_fields:
            if field in branding_data:
                setattr(branding, field, branding_data[field])
                updated.append(field)
        # Also accept the frontend URL field names
        for fe_key, model_field in url_field_map.items():
            if fe_key in branding_data and model_field not in updated:
                val = branding_data[fe_key]
                if val:  # Only set if non-empty
                    setattr(branding, model_field, val)
                    updated.append(model_field)
        if updated:
            branding.save(update_fields=updated + ['updated_at'])

    # Save stake tiers
    tiers_data = request.data.get('stake_tiers', [])
    if tiers_data and game_config and game_config.currency:
        existing_tier_ids = set()
        for td in tiers_data:
            tier_id = td.get('id')
            if tier_id:
                try:
                    t = StakeTier.objects.get(id=tier_id, currency=game_config.currency)
                except StakeTier.DoesNotExist:
                    continue
            else:
                t = StakeTier(currency=game_config.currency)

            t.name = td.get('name', 'Tier')
            t.min_stake = Decimal(str(td.get('min_stake', 0)))
            t.max_stake = Decimal(str(td.get('max_stake', 0)))
            t.display_order = td.get('display_order', 0)
            t.is_active = td.get('is_active', True)
            t.save()

            # Update M2M denominations
            denom_ids = td.get('denomination_ids', [])
            if denom_ids is not None:
                t.denominations.set(
                    CurrencyDenomination.objects.filter(id__in=denom_ids, currency=game_config.currency)
                )

            existing_tier_ids.add(t.id)

        # Delete tiers removed from list
        if existing_tier_ids:
            StakeTier.objects.filter(
                currency=game_config.currency
            ).exclude(id__in=existing_tier_ids).delete()

    # Save legal documents
    from game.models import LegalDocument
    legal_data = request.data.get('legal', {})
    if legal_data:
        legal = LegalDocument.get_legal()
        legal_fields = ['privacy_policy', 'terms_of_service', 'sms_disclosure',
                        'support_email', 'support_phone', 'company_name',
                        'company_address', 'license_info']
        updated = []
        for field in legal_fields:
            if field in legal_data:
                setattr(legal, field, legal_data[field])
                updated.append(field)
        if updated:
            legal.save(update_fields=updated + ['updated_at'])

    return Response({'status': 'saved'})


@api_view(['POST'])
@permission_classes([IsStaffAdmin])
def branding_upload(request):
    """Upload branding files (logo, favicon/icon, loading animation)."""
    from game.models import SiteBranding
    branding = SiteBranding.get_branding()

    field_map = {
        'logo': 'logo',
        'logo_icon': 'logo_icon',
        'loading_animation': 'loading_animation',
        'regulatory_logo': 'regulatory_logo',
    }

    updated = []
    for param, model_field in field_map.items():
        if param in request.FILES:
            file = request.FILES[param]
            getattr(branding, model_field).save(file.name, file, save=False)
            updated.append(model_field)

    if updated:
        branding.save(update_fields=updated + ['updated_at'])

    return Response({
        'status': 'uploaded',
        'logo_url': branding.logo.url if branding.logo else '',
        'logo_icon_url': branding.logo_icon.url if branding.logo_icon else '',
        'loading_animation_url': branding.loading_animation.url if branding.loading_animation else '',
        'regulatory_logo_url': branding.regulatory_logo.url if branding.regulatory_logo else '',
    })


@api_view(['POST'])
@permission_classes([IsStaffAdmin])
def cloudinary_upload(request):
    """Upload any image/GIF to Cloudinary and return the CDN URL.
    
    Body (multipart): file=<file>, folder=<cloudinary_folder>
    Returns: { url: 'https://res.cloudinary.com/...' }
    """
    import cloudinary.uploader
    from django.conf import settings as django_settings

    cld_cloud = getattr(django_settings, 'CLOUDINARY_CLOUD_NAME', '') or os.getenv('CLOUDINARY_CLOUD_NAME', '')
    cld_key = getattr(django_settings, 'CLOUDINARY_API_KEY', '') or os.getenv('CLOUDINARY_API_KEY', '')
    cld_secret = getattr(django_settings, 'CLOUDINARY_API_SECRET', '') or os.getenv('CLOUDINARY_API_SECRET', '')

    if not cld_cloud or not cld_key:
        return Response({'error': 'Cloudinary not configured'}, status=400)

    cloudinary.config(cloud_name=cld_cloud, api_key=cld_key, api_secret=cld_secret)

    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=400)

    file = request.FILES['file']
    folder = request.data.get('folder', 'cashflip/uploads')
    # Use filename without extension as public_id
    import os as _os
    name = _os.path.splitext(file.name)[0]
    public_id = f"{folder}/{name}"

    try:
        result = cloudinary.uploader.upload(
            file,
            public_id=public_id,
            resource_type='auto',
            overwrite=True,
        )
        return Response({
            'url': result['secure_url'],
            'public_id': result['public_id'],
            'format': result.get('format', ''),
            'width': result.get('width', 0),
            'height': result.get('height', 0),
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST', 'PATCH', 'DELETE'])
@permission_classes([IsStaffAdmin])
def simulated_config_manage(request, config_id=None):
    """Create, update, or delete simulated game configs."""
    if request.method == 'POST' and config_id is None:
        sc = SimulatedGameConfig.objects.create(
            name=request.data.get('name', 'New Test Config'),
            is_enabled=request.data.get('is_enabled', False),
            outcome_mode=request.data.get('outcome_mode', 'normal'),
        )
        return Response({'id': sc.id, 'status': 'created'}, status=status.HTTP_201_CREATED)

    if config_id is None:
        return Response({'error': 'Config ID required'}, status=400)

    try:
        sc = SimulatedGameConfig.objects.get(id=config_id)
    except SimulatedGameConfig.DoesNotExist:
        return Response({'error': 'Config not found'}, status=404)

    if request.method == 'DELETE':
        sc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PATCH
    fields_map = {
        'name': 'name', 'is_enabled': 'is_enabled', 'outcome_mode': 'outcome_mode',
        'force_zero_at_flip': 'force_zero_at_flip', 'fixed_zero_probability': 'fixed_zero_probability',
        'win_streak_length': 'win_streak_length', 'force_denomination_value': 'force_denomination_value',
        'apply_to_all_players': 'apply_to_all_players', 'override_min_stake': 'override_min_stake',
        'override_max_cashout': 'override_max_cashout', 'grant_test_balance': 'grant_test_balance',
        'auto_disable_after': 'auto_disable_after', 'notes': 'notes',
    }
    updated = []
    for key, field in fields_map.items():
        if key in request.data:
            val = request.data[key]
            if val == '' and field in ('force_denomination_value', 'override_min_stake', 'override_max_cashout'):
                val = None
            setattr(sc, field, val)
            updated.append(field)
    if updated:
        sc.save(update_fields=updated + ['updated_at'])

    # If enabling this config, disable all others
    if 'is_enabled' in request.data and request.data['is_enabled']:
        SimulatedGameConfig.objects.exclude(id=sc.id).update(is_enabled=False)

    return Response({'status': 'updated'})


# ==================== STAFF MANAGEMENT ====================

@api_view(['POST'])
@permission_classes([IsStaffAdmin])
def create_staff(request):
    """Create a new staff member from an existing player account."""
    phone = request.data.get('phone', '')
    role_codename = request.data.get('role', '')

    if not phone or not role_codename:
        return Response({'error': 'Phone and role are required'}, status=400)

    try:
        player = Player.objects.get(phone=phone)
    except Player.DoesNotExist:
        return Response({'error': f'No player found with phone {phone}'}, status=404)

    try:
        role = AdminRole.objects.get(codename=role_codename)
    except AdminRole.DoesNotExist:
        return Response({'error': f'Role "{role_codename}" not found'}, status=404)

    if StaffMember.objects.filter(player=player).exists():
        return Response({'error': 'This player is already a staff member'}, status=400)

    player.is_staff = True
    player.save(update_fields=['is_staff'])

    sm = StaffMember.objects.create(player=player, role=role, is_active=True)
    return Response({'status': 'created', 'id': str(sm.player.id)}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsStaffAdmin])
def create_role(request):
    """Create a new admin role."""
    name = request.data.get('name', '')
    codename = request.data.get('codename', '')
    permissions = request.data.get('permissions', [])
    description = request.data.get('description', '')

    if not name or not codename:
        return Response({'error': 'Name and codename are required'}, status=400)

    if AdminRole.objects.filter(codename=codename).exists():
        return Response({'error': f'Role with codename "{codename}" already exists'}, status=400)

    role = AdminRole.objects.create(
        name=name, codename=codename,
        permissions=permissions, description=description,
    )
    return Response(RoleSerializer(role).data, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsStaffAdmin])
def delete_staff(request, user_id):
    """Remove a staff member (doesn't delete the player account)."""
    try:
        sm = StaffMember.objects.get(player_id=user_id)
    except StaffMember.DoesNotExist:
        return Response({'error': 'Staff member not found'}, status=404)

    sm.player.is_staff = False
    sm.player.save(update_fields=['is_staff'])
    sm.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== GLOBAL SEARCH ====================

@api_view(['GET'])
@permission_classes([IsStaffAdmin])
def global_search(request):
    q = request.query_params.get('q', '').strip()
    if len(q) < 2:
        return Response({'results': []})

    results = []

    # Search players
    players = Player.objects.filter(
        Q(phone__icontains=q) | Q(display_name__icontains=q),
        is_staff=False, is_superuser=False,
    ).order_by('-date_joined')[:5]
    for p in players:
        wallet = getattr(p, 'wallet', None)
        results.append({
            'type': 'player',
            'id': str(p.id),
            'title': p.get_display_name(),
            'subtitle': p.phone or '',
            'meta': f'Balance: GHS {wallet.balance if wallet else 0}',
            'url': '/players',
        })

    # Search game sessions by player
    sessions = GameSession.objects.select_related('player').filter(
        Q(player__phone__icontains=q) | Q(player__display_name__icontains=q),
    ).order_by('-created_at')[:5]
    for s in sessions:
        results.append({
            'type': 'session',
            'id': str(s.id),
            'title': f'Session #{str(s.id)[:8]}',
            'subtitle': f'{s.player.get_display_name()} — {s.status}',
            'meta': f'Stake: GHS {s.stake_amount}',
            'url': '/sessions',
        })

    # Search deposits/withdrawals by phone or reference
    for dep in Deposit.objects.select_related('player').filter(
        Q(player__phone__icontains=q) | Q(orchard_reference__icontains=q) | Q(paystack_reference__icontains=q),
    ).order_by('-created_at')[:3]:
        ref = dep.orchard_reference or dep.paystack_reference or str(dep.id)[:8]
        results.append({
            'type': 'transaction',
            'id': str(dep.id),
            'title': f'Deposit {ref}',
            'subtitle': f'{dep.player.get_display_name()} — {dep.status}',
            'meta': f'GHS {dep.amount}',
            'url': '/transactions',
        })
    for wdr in Withdrawal.objects.select_related('player').filter(
        Q(player__phone__icontains=q) | Q(payout_reference__icontains=q),
    ).order_by('-created_at')[:3]:
        ref = wdr.payout_reference or str(wdr.id)[:8]
        results.append({
            'type': 'transaction',
            'id': str(wdr.id),
            'title': f'Withdrawal {ref}',
            'subtitle': f'{wdr.player.get_display_name()} — {wdr.status}',
            'meta': f'GHS {wdr.amount}',
            'url': '/transactions',
        })

    # Search partners
    try:
        from partner.models import Operator
        for op in Operator.objects.filter(
            Q(name__icontains=q) | Q(slug__icontains=q),
        )[:3]:
            results.append({
                'type': 'partner',
                'id': str(op.id),
                'title': op.name,
                'subtitle': op.slug,
                'meta': f'Status: {op.status}',
                'url': '/partners',
            })
    except ImportError:
        pass

    return Response({'results': results[:15]})


# ==================== NOTIFICATIONS ====================

@api_view(['GET'])
@permission_classes([IsStaffAdmin])
def notifications_list(request):
    """Generate real-time notifications from system events."""
    notifications = []
    now = timezone.now()
    today = now.date()

    # Pending withdrawals
    pending_wdrs = Withdrawal.objects.filter(status='pending').order_by('-created_at')
    pending_count = pending_wdrs.count()
    if pending_count > 0:
        total_pending = pending_wdrs.aggregate(s=Sum('amount'))['s'] or 0
        latest = pending_wdrs.first()
        notifications.append({
            'id': f'pending-wdr-{today}',
            'type': 'warning',
            'title': f'{pending_count} Pending Withdrawal{"s" if pending_count > 1 else ""}',
            'message': f'GHS {total_pending} total awaiting approval',
            'url': '/finance',
            'created_at': latest.created_at.isoformat() if latest else now.isoformat(),
            'read': False,
        })

    # New signups today
    new_today = Player.objects.filter(date_joined__date=today, is_staff=False).count()
    if new_today > 0:
        notifications.append({
            'id': f'signups-{today}',
            'type': 'info',
            'title': f'{new_today} New Player{"s" if new_today > 1 else ""} Today',
            'message': f'{new_today} players signed up today',
            'url': '/players',
            'created_at': now.isoformat(),
            'read': False,
        })

    # Large wins (cashout > 500 in last 24h)
    big_wins = GameSession.objects.filter(
        status='cashed_out',
        cashout_balance__gte=500,
        created_at__gte=now - timedelta(hours=24),
    ).select_related('player').order_by('-cashout_balance')[:3]
    for win in big_wins:
        notifications.append({
            'id': f'bigwin-{win.id}',
            'type': 'alert',
            'title': f'Large Win: GHS {win.cashout_balance}',
            'message': f'{win.player.get_display_name()} cashed out GHS {win.cashout_balance}',
            'url': '/sessions',
            'created_at': win.created_at.isoformat(),
            'read': False,
        })

    # Failed deposits in last 24h
    failed_deps = Deposit.objects.filter(
        status='failed',
        created_at__gte=now - timedelta(hours=24),
    ).count()
    if failed_deps > 0:
        notifications.append({
            'id': f'failed-deps-{today}',
            'type': 'danger',
            'title': f'{failed_deps} Failed Deposit{"s" if failed_deps > 1 else ""}',
            'message': f'{failed_deps} deposits failed in the last 24 hours',
            'url': '/transactions',
            'created_at': now.isoformat(),
            'read': False,
        })

    # Active simulation config warning
    sim_config = SimulatedGameConfig.get_active_config()
    if sim_config:
        notifications.append({
            'id': f'sim-active-{sim_config.id}',
            'type': 'warning',
            'title': 'Simulation Mode Active',
            'message': f'"{sim_config.name}" is overriding game outcomes ({sim_config.get_outcome_mode_display()})',
            'url': '/settings',
            'created_at': sim_config.updated_at.isoformat(),
            'read': False,
        })

    # Revenue milestone
    revenue_today = (
        (Deposit.objects.filter(created_at__date=today, status='completed').aggregate(s=Sum('amount'))['s'] or Decimal('0'))
        - (Withdrawal.objects.filter(created_at__date=today, status='completed').aggregate(s=Sum('amount'))['s'] or Decimal('0'))
    )
    if revenue_today > 1000:
        notifications.append({
            'id': f'revenue-{today}',
            'type': 'success',
            'title': f'Revenue Milestone: GHS {revenue_today}',
            'message': f'Today\'s net revenue has crossed GHS 1,000',
            'url': '/',
            'created_at': now.isoformat(),
            'read': False,
        })

    # Sort by created_at descending
    notifications.sort(key=lambda x: x['created_at'], reverse=True)

    return Response({
        'notifications': notifications[:20],
        'unread_count': len([n for n in notifications if not n['read']]),
    })


# ==================== Live Activity (Polling) ====================

@api_view(['GET'])
@permission_classes([IsStaffAdmin])
def live_activity(request):
    """
    Real-time activity feed for admin dashboard.
    Returns live players, active sessions, recent flips, recent deposits/withdrawals.
    Designed for 3-5s polling interval.
    """
    now = timezone.now()
    five_min_ago = now - timedelta(minutes=5)
    one_min_ago = now - timedelta(minutes=1)
    today = now.date()

    # Active sessions right now
    active_sessions = GameSession.objects.filter(status='active').select_related('player', 'currency')
    active_count = active_sessions.count()

    # Live players (sessions active in last 5 min)
    live_players_qs = active_sessions.filter(
        updated_at__gte=five_min_ago
    ).order_by('-updated_at')[:20]

    live_players = []
    for s in live_players_qs:
        last_flip = FlipResult.objects.filter(session=s).order_by('-created_at').first()
        live_players.append({
            'session_id': str(s.id),
            'player_id': str(s.player_id),
            'player_name': s.player.display_name or s.player.phone[:8] + '***',
            'stake': str(s.stake_amount),
            'balance': str(s.cashout_balance),
            'flips': s.flip_count,
            'currency': s.currency.symbol if s.currency else 'GH₵',
            'last_flip_at': last_flip.created_at.isoformat() if last_flip else s.created_at.isoformat(),
            'started_at': s.created_at.isoformat(),
        })

    # Recent flips (last 60 seconds)
    recent_flips = FlipResult.objects.filter(
        created_at__gte=one_min_ago
    ).select_related('session__player', 'session__currency').order_by('-created_at')[:30]

    flip_feed = []
    for f in recent_flips:
        flip_feed.append({
            'id': str(f.id) if hasattr(f, 'id') else f.flip_number,
            'player_name': f.session.player.display_name or f.session.player.phone[:8] + '***',
            'value': str(f.value),
            'is_zero': f.is_zero,
            'flip_number': f.flip_number,
            'session_id': str(f.session_id),
            'currency': f.session.currency.symbol if f.session.currency else 'GH₵',
            'timestamp': f.created_at.isoformat(),
        })

    # Recent deposits & withdrawals (last 5 min)
    recent_deps = Deposit.objects.filter(
        created_at__gte=five_min_ago
    ).select_related('player').order_by('-created_at')[:10]

    recent_wdrs = Withdrawal.objects.filter(
        created_at__gte=five_min_ago
    ).select_related('player').order_by('-created_at')[:10]

    money_feed = []
    for d in recent_deps:
        money_feed.append({
            'type': 'deposit',
            'player_name': d.player.display_name or d.player.phone[:8] + '***',
            'amount': str(d.amount),
            'status': d.status,
            'timestamp': d.created_at.isoformat(),
        })
    for w in recent_wdrs:
        money_feed.append({
            'type': 'withdrawal',
            'player_name': w.player.display_name or w.player.phone[:8] + '***',
            'amount': str(w.amount),
            'status': w.status,
            'timestamp': w.created_at.isoformat(),
        })
    money_feed.sort(key=lambda x: x['timestamp'], reverse=True)

    # Quick stats (today)
    sessions_today = GameSession.objects.filter(created_at__date=today).count()
    flips_today = FlipResult.objects.filter(created_at__date=today).count()
    stakes_today = GameSession.objects.filter(
        created_at__date=today
    ).aggregate(s=Sum('stake_amount'))['s'] or Decimal('0')
    payouts_today = GameSession.objects.filter(
        created_at__date=today, status__in=['cashed_out', 'completed']
    ).aggregate(s=Sum('cashout_balance'))['s'] or Decimal('0')

    return Response({
        'timestamp': now.isoformat(),
        'active_sessions': active_count,
        'live_players': live_players,
        'flip_feed': flip_feed,
        'money_feed': money_feed[:15],
        'today': {
            'sessions': sessions_today,
            'flips': flips_today,
            'total_staked': str(stakes_today),
            'total_paid_out': str(payouts_today),
            'ggr': str(stakes_today - payouts_today),
        },
    })


# ==================== SMS Providers CRUD ====================

def _serialize_sms_provider(p):
    return {
        'id': p.id,
        'name': p.name,
        'provider_type': p.provider_type,
        'provider_type_display': p.get_provider_type_display(),
        'api_key': p.api_key[:8] + '***' if p.api_key else '',
        'api_secret_set': bool(p.api_secret),
        'sender_id': p.sender_id,
        'base_url': p.base_url,
        'is_active': p.is_active,
        'priority': p.priority,
        'extra_config': p.extra_config,
        'created_at': p.created_at.isoformat() if p.created_at else None,
        'updated_at': p.updated_at.isoformat() if p.updated_at else None,
    }


@api_view(['GET', 'POST'])
@permission_classes([IsStaffAdmin])
def sms_providers(request):
    """List all SMS providers or create a new one."""
    if request.method == 'GET':
        providers = SMSProvider.objects.all().order_by('-priority', 'name')
        return Response({'providers': [_serialize_sms_provider(p) for p in providers]})

    # POST — create
    data = request.data
    required = ['name', 'provider_type', 'api_key']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return Response({'error': f'Missing fields: {", ".join(missing)}'}, status=status.HTTP_400_BAD_REQUEST)

    provider = SMSProvider.objects.create(
        name=data['name'],
        provider_type=data['provider_type'],
        api_key=data['api_key'],
        api_secret=data.get('api_secret', ''),
        sender_id=data.get('sender_id', 'CASHFLIP'),
        base_url=data.get('base_url', ''),
        is_active=data.get('is_active', True),
        priority=data.get('priority', 0),
        extra_config=data.get('extra_config', {}),
    )
    return Response({'provider': _serialize_sms_provider(provider)}, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsStaffAdmin])
def sms_provider_detail(request, pk):
    """Get, update, or delete a single SMS provider."""
    try:
        provider = SMSProvider.objects.get(pk=pk)
    except SMSProvider.DoesNotExist:
        return Response({'error': 'Provider not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response({'provider': _serialize_sms_provider(provider)})

    if request.method == 'DELETE':
        provider.delete()
        return Response({'success': True})

    # PUT — update (skip blank api_key/api_secret to allow partial updates)
    data = request.data
    updatable = ['name', 'provider_type', 'api_key', 'api_secret', 'sender_id',
                 'base_url', 'is_active', 'priority', 'extra_config']
    changed = []
    for field in updatable:
        if field in data:
            val = data[field]
            if field in ('api_key', 'api_secret') and not val:
                continue
            setattr(provider, field, val)
            changed.append(field)
    if changed:
        provider.save()
    return Response({'provider': _serialize_sms_provider(provider)})


# ==================== Math Validation ====================

@api_view(['GET'])
@permission_classes([IsStaffAdmin])
def validate_house_edge(request):
    """
    Compute theoretical house edge from current zero curve params + denomination multiplier weights.
    Returns deviation from configured target.
    """
    import math

    game_config = GameConfig.objects.filter(is_active=True).first()
    if not game_config:
        return Response({'error': 'No active game config'}, status=status.HTTP_404_NOT_FOUND)

    from game.models import CurrencyDenomination
    denoms = CurrencyDenomination.objects.filter(
        currency=game_config.currency, is_active=True, is_zero=False
    )

    # Weighted average multiplier
    total_weight = sum(d.weight for d in denoms)
    if total_weight == 0:
        return Response({'error': 'No active denominations'}, status=status.HTTP_400_BAD_REQUEST)

    weighted_mult = sum(float(d.payout_multiplier) * d.weight for d in denoms) / total_weight

    # Estimate expected surviving flips using the zero sigmoid curve
    # P(zero at flip n) = base_rate / (1 + e^(-growth_rate * (n - mid)))
    # For simplicity, simulate expected flips
    base_rate = float(game_config.zero_base_rate)
    growth_rate = float(game_config.zero_growth_rate)
    min_flips_zero = game_config.min_flips_before_zero

    # Monte Carlo-ish: compute expected flips analytically
    # P(survive flip n) = product of (1 - P_zero(i)) for i=1..n
    # P_zero(i) = 0 if i < min_flips_zero, else base_rate / (1 + e^(-growth_rate * (i - 10)))
    expected_flips = 0.0
    survive_prob = 1.0
    max_flips = 200

    for n in range(1, max_flips + 1):
        if n <= min_flips_zero:
            p_zero = 0.0
        else:
            p_zero = base_rate / (1 + math.exp(-growth_rate * (n - 10)))
        p_zero = min(p_zero, 1.0)
        survive_prob *= (1 - p_zero)
        expected_flips += survive_prob
        if survive_prob < 0.001:
            break

    expected_payout_pct = expected_flips * weighted_mult  # in percentage points
    theoretical_house_edge = 100.0 - expected_payout_pct
    configured_target = float(game_config.house_edge_percent)
    deviation = theoretical_house_edge - configured_target

    if abs(deviation) < 5:
        edge_status = 'OK'
    elif abs(deviation) < 10:
        edge_status = 'WARNING'
    else:
        edge_status = 'CRITICAL'

    return Response({
        'weighted_avg_multiplier': round(weighted_mult, 2),
        'expected_surviving_flips': round(expected_flips, 2),
        'expected_payout_pct': round(expected_payout_pct, 1),
        'theoretical_house_edge': round(theoretical_house_edge, 1),
        'configured_target': configured_target,
        'deviation': round(deviation, 1),
        'status': edge_status,
        'denominations': [
            {'value': str(d.value), 'multiplier': str(d.payout_multiplier), 'weight': d.weight}
            for d in denoms.order_by('value')
        ],
        'zero_curve': {
            'base_rate': str(game_config.zero_base_rate),
            'growth_rate': str(game_config.zero_growth_rate),
            'min_flips_before_zero': min_flips_zero,
        },
    })
