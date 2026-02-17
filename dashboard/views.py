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

from accounts.models import Player, AdminRole, StaffMember, AuthConfig, PlayerProfile
from game.models import GameSession, FlipResult, Currency
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


@api_view(['PATCH'])
@permission_classes([IsStaffAdmin])
def player_update(request, player_id):
    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        return Response({'error': 'Player not found'}, status=404)

    if 'is_active' in request.data:
        player.is_active = request.data['is_active']
        player.save(update_fields=['is_active'])

    return Response(PlayerListSerializer(player).data)


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
            dep_qs = dep_qs.filter(Q(player__phone__icontains=search) | Q(reference__icontains=search))
        for d in dep_qs[:100]:
            items.append({
                'id': str(d.id),
                'player_name': d.player.get_display_name(),
                'player_phone': d.player.phone or '',
                'type': 'deposit',
                'amount': str(d.amount),
                'currency': 'GHS',
                'status': d.status,
                'reference': d.reference or '',
                'provider': d.provider if hasattr(d, 'provider') else 'mobile_money',
                'created_at': d.created_at.isoformat(),
            })

    # Withdrawals
    if type_filter in ('', 'withdrawal'):
        wdr_qs = Withdrawal.objects.select_related('player').order_by('-created_at')
        if search:
            wdr_qs = wdr_qs.filter(Q(player__phone__icontains=search) | Q(reference__icontains=search))
        for w in wdr_qs[:100]:
            items.append({
                'id': str(w.id),
                'player_name': w.player.get_display_name(),
                'player_phone': w.player.phone or '',
                'type': 'withdrawal',
                'amount': str(w.amount),
                'currency': 'GHS',
                'status': w.status,
                'reference': w.reference or '',
                'provider': w.provider if hasattr(w, 'provider') else 'mobile_money',
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
    total_deposits = Deposit.objects.filter(status='completed').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    total_withdrawals = Withdrawal.objects.filter(status='completed').aggregate(s=Sum('amount'))['s'] or Decimal('0')

    pending_wdrs = Withdrawal.objects.filter(status='pending')
    pending_total = pending_wdrs.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    pending_count = pending_wdrs.count()

    pending_list = []
    for w in pending_wdrs.select_related('player').order_by('-created_at')[:20]:
        pending_list.append({
            'id': str(w.id),
            'player_name': w.player.get_display_name(),
            'type': 'withdrawal',
            'amount': str(w.amount),
            'status': w.status,
            'provider': getattr(w, 'provider', 'mobile_money'),
            'created_at': w.created_at.isoformat(),
        })

    recent = []
    for d in Deposit.objects.select_related('player').filter(status='completed').order_by('-created_at')[:5]:
        recent.append({
            'id': str(d.id), 'player_name': d.player.get_display_name(),
            'type': 'deposit', 'amount': str(d.amount), 'status': d.status,
            'provider': getattr(d, 'provider', 'mobile_money'),
            'created_at': d.created_at.isoformat(),
        })
    for w in Withdrawal.objects.select_related('player').filter(status='completed').order_by('-created_at')[:5]:
        recent.append({
            'id': str(w.id), 'player_name': w.player.get_display_name(),
            'type': 'withdrawal', 'amount': str(w.amount), 'status': w.status,
            'provider': getattr(w, 'provider', 'mobile_money'),
            'created_at': w.created_at.isoformat(),
        })
    recent.sort(key=lambda x: x['created_at'], reverse=True)

    return Response({
        'stats': {
            'total_deposits': str(total_deposits),
            'total_withdrawals': str(total_withdrawals),
            'net_revenue': str(total_deposits - total_withdrawals),
            'pending_withdrawals': str(pending_total),
            'pending_count': pending_count,
        },
        'pending_withdrawals': pending_list,
        'recent': recent[:10],
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

@api_view(['GET'])
@permission_classes([IsStaffAdmin])
def partner_list(request):
    try:
        from partner.models import Operator, OperatorSession
    except ImportError:
        return Response({'results': [], 'count': 0})

    operators = Operator.objects.all().order_by('-created_at')
    results = []
    for op in operators:
        sessions_count = OperatorSession.objects.filter(operator=op).count()
        results.append({
            'id': str(op.id),
            'name': op.name,
            'slug': op.slug,
            'website': op.website or '',
            'status': op.status,
            'commission_percent': str(op.commission_percent),
            'settlement_frequency': op.settlement_frequency,
            'total_sessions': sessions_count,
            'total_revenue': '0.00',
            'api_keys_count': op.api_keys.filter(is_active=True).count(),
            'created_at': op.created_at.isoformat(),
        })

    return Response({'results': results, 'count': len(results)})


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

    return Response({
        'summary': {
            'total_ggr': str(total_ggr),
            'avg_session_value': str(round(avg_session, 2)),
            'avg_flips_per_session': round(avg_flips, 1),
            'house_edge_actual': str(round(float(total_ggr) / max(float(total_stakes), 1) * 100, 1)),
            'retention_7d': str(retention),
        },
        'daily_revenue': revenue_chart,
        'daily_players': player_chart,
        'top_denominations': [],
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

    if request.method == 'GET':
        return Response({
            'auth': AuthSettingsSerializer(auth_config).data,
            'game': {
                'house_edge_percent': '60.00',
                'min_stake': '1.00',
                'max_stake': '1000.00',
                'zero_base_rate': '0.05',
                'max_multiplier': '100',
            },
        })

    # POST — save settings
    auth_data = request.data.get('auth', {})
    if auth_data:
        for field in ['sms_otp_enabled', 'whatsapp_otp_enabled', 'google_enabled',
                      'facebook_enabled', 'otp_expiry_minutes', 'max_otp_per_hour']:
            if field in auth_data:
                setattr(auth_config, field, auth_data[field])
        auth_config.save()

    return Response({'status': 'saved'})
