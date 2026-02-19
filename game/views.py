"""
Game API Views - Start, Flip, Cashout, Pause, Resume, History, Verify
"""

import logging
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from game.engine import execute_flip
from game.models import (
    Currency, CurrencyDenomination, GameConfig, SimulatedGameConfig,
    GameSession, FlipResult, Badge, PlayerBadge, DailyBonusConfig,
    DailyBonusSpin, FeatureConfig,
)
from game.serializers import (
    StartGameSerializer, GameSessionSerializer, GameSessionListSerializer,
    GameConfigPublicSerializer, CurrencySerializer, PauseSerializer,
)

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def currencies(request):
    """List active currencies."""
    qs = Currency.objects.filter(is_active=True)
    return Response(CurrencySerializer(qs, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def game_config(request):
    """Get game config for a currency, including denominations."""
    code = request.query_params.get('currency', 'GHS')
    try:
        config = GameConfig.objects.select_related('currency').get(
            currency__code=code, is_active=True
        )
    except GameConfig.DoesNotExist:
        return Response({'error': 'Game config not found'}, status=status.HTTP_404_NOT_FOUND)

    from game.serializers import DenominationSerializer
    denoms = CurrencyDenomination.objects.filter(
        currency=config.currency, is_active=True
    ).order_by('display_order', 'value')
    data = GameConfigPublicSerializer(config).data
    data['denominations'] = DenominationSerializer(denoms, many=True).data
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_game(request):
    """Start a new game session."""
    serializer = StartGameSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    player = request.user
    stake_amount = serializer.validated_data['stake_amount']
    currency_code = serializer.validated_data['currency_code']
    client_seed = serializer.validated_data.get('client_seed', '')

    # Check no active session
    active = GameSession.objects.filter(player=player, status__in=['active', 'paused']).first()
    if active:
        return Response(
            {'error': 'You have an active game session', 'session_id': str(active.id)},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get currency and config
    try:
        currency = Currency.objects.get(code=currency_code, is_active=True)
        config = GameConfig.objects.get(currency=currency, is_active=True)
    except (Currency.DoesNotExist, GameConfig.DoesNotExist):
        return Response({'error': 'Currency not available'}, status=status.HTTP_400_BAD_REQUEST)

    # Check for active simulation config
    sim = SimulatedGameConfig.get_active_config()
    sim_active = sim and sim.applies_to_player(player)

    # Apply limit overrides from simulation
    effective_min_stake = sim.override_min_stake if (sim_active and sim.override_min_stake is not None) else config.min_stake

    if stake_amount < effective_min_stake:
        return Response(
            {'error': f'Minimum stake is {currency.symbol}{effective_min_stake}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # All wallet operations in a single atomic transaction to prevent
    # race conditions and ensure select_for_update works correctly.
    from wallet.models import Wallet, WalletTransaction

    try:
        with transaction.atomic():
            # Lock wallet row — prevents concurrent game starts
            try:
                wallet = Wallet.objects.select_for_update().get(player=player)
            except Wallet.DoesNotExist:
                return Response({'error': 'Wallet not found. Please make a deposit first.'}, status=status.HTTP_400_BAD_REQUEST)

            # Re-check active session inside transaction (double-start guard)
            if GameSession.objects.filter(player=player, status__in=['active', 'paused']).exists():
                return Response(
                    {'error': 'You already have an active game session'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Grant test balance if simulation is active and configured
            if sim_active and sim.grant_test_balance > 0:
                grant_amount = sim.grant_test_balance
                if wallet.balance < grant_amount:
                    balance_before = wallet.balance
                    wallet.balance = grant_amount
                    wallet.save(update_fields=['balance', 'updated_at'])
                    tx_ref = f'CF-TEST-{uuid.uuid4().hex[:8].upper()}'
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=grant_amount - balance_before,
                        tx_type='test_credit',
                        reference=tx_ref,
                        balance_before=balance_before,
                        balance_after=wallet.balance,
                        metadata={'sim_config': sim.name},
                    )
                    logger.info(f'[SIM] Granted test balance {grant_amount} to {player.phone}')

            # Balance check with wallet row locked — no race condition
            if wallet.available_balance < stake_amount:
                return Response(
                    {'error': f'Insufficient balance. Available: {currency.symbol}{wallet.available_balance}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Deduct stake from wallet
            balance_before = wallet.balance
            wallet.balance -= stake_amount
            wallet.locked_balance += stake_amount
            wallet.save(update_fields=['balance', 'locked_balance', 'updated_at'])

            tx_ref = f'CF-STAKE-{uuid.uuid4().hex[:8].upper()}'
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=-stake_amount,
                tx_type='stake',
                reference=tx_ref,
                balance_before=balance_before,
                balance_after=wallet.balance,
                metadata={'currency': currency_code},
            )

            # Create session
            session = GameSession.objects.create(
                player=player,
                currency=currency,
                stake_amount=stake_amount,
                status='active',
                client_seed=client_seed,
            )
            session.generate_seeds()

            # Track simulation usage
            if sim_active:
                sim.increment_usage()

    except Exception as e:
        logger.error(f'start_game transaction failed for {player.phone}: {e}')
        return Response({'error': 'Failed to start game. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    response_data = {
        'session_id': str(session.id),
        'server_seed_hash': session.server_seed_hash,
        'stake_amount': str(stake_amount),
        'currency': CurrencySerializer(currency).data,
    }
    if sim_active:
        response_data['simulation_active'] = True
        response_data['simulation_mode'] = sim.get_outcome_mode_display()

    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def flip(request):
    """Execute a flip in the active game session."""
    player = request.user
    session = GameSession.objects.filter(player=player, status='active').first()

    if not session:
        return Response({'error': 'No active game session'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = execute_flip(session)
    except Exception as e:
        logger.error(f'execute_flip crashed for session {session.id}: {e}', exc_info=True)
        # Session may have been saved as 'lost' before the crash — release locked funds
        session.refresh_from_db()
        if session.status == 'lost':
            from wallet.models import Wallet
            try:
                with transaction.atomic():
                    wallet = Wallet.objects.select_for_update().get(player=player)
                    wallet.locked_balance = max(Decimal('0'), wallet.locked_balance - session.stake_amount)
                    wallet.save(update_fields=['locked_balance', 'updated_at'])
            except Wallet.DoesNotExist:
                pass
        return Response({'error': 'Flip failed. Please try again.', 'success': False},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if not result.get('success'):
        return Response({'error': result.get('error', 'Flip failed')}, status=status.HTTP_400_BAD_REQUEST)

    # If lost, unlock the stake (it's gone)
    if result['is_zero']:
        from wallet.models import Wallet
        try:
            with transaction.atomic():
                wallet = Wallet.objects.select_for_update().get(player=player)
                wallet.locked_balance = max(Decimal('0'), wallet.locked_balance - session.stake_amount)
                wallet.save(update_fields=['locked_balance', 'updated_at'])
        except Wallet.DoesNotExist:
            pass

    # Check for badge awards
    try:
        new_badges = check_and_award_badges(player, session=session, flip_data=result)
        if new_badges:
            result['new_badges'] = new_badges
    except Exception:
        pass

    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cashout(request):
    """Cash out the current game session."""
    player = request.user
    session = GameSession.objects.filter(player=player, status='active').first()

    if not session:
        return Response({'error': 'No active game session'}, status=status.HTTP_400_BAD_REQUEST)

    if session.cashout_balance <= 0:
        return Response({'error': 'Nothing to cash out'}, status=status.HTTP_400_BAD_REQUEST)

    from wallet.models import Wallet, WalletTransaction

    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(player=player)
        cashout_amount = session.cashout_balance

        # Credit wallet
        balance_before = wallet.balance
        wallet.balance += cashout_amount
        wallet.locked_balance = max(Decimal('0'), wallet.locked_balance - session.stake_amount)
        wallet.save(update_fields=['balance', 'locked_balance', 'updated_at'])

        tx_ref = f'CF-WIN-{uuid.uuid4().hex[:8].upper()}'
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=cashout_amount,
            tx_type='cashout',
            reference=tx_ref,
            balance_before=balance_before,
            balance_after=wallet.balance,
            metadata={'session_id': str(session.id)},
        )

        # End session
        session.status = 'cashed_out'
        session.ended_at = timezone.now()
        session.save(update_fields=['status', 'ended_at'])

        # Update player profile
        from accounts.models import PlayerProfile
        profile, _ = PlayerProfile.objects.get_or_create(player=player)
        profile.total_games += 1
        profile.total_won += 1
        profile.lifetime_flips += session.flip_count
        if cashout_amount > profile.highest_cashout:
            profile.highest_cashout = cashout_amount
        profile.save()

    # Check for badge awards on cashout
    resp_data = {
        'cashout_amount': str(cashout_amount),
        'new_balance': str(wallet.balance),
        'session_id': str(session.id),
    }
    try:
        new_badges = check_and_award_badges(player, session=session, flip_data={
            'cashout_amount': float(cashout_amount),
        })
        if new_badges:
            resp_data['new_badges'] = new_badges
    except Exception:
        pass

    return Response(resp_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pause_game(request):
    """Pause the current game session (costs a fee)."""
    player = request.user
    session = GameSession.objects.filter(player=player, status='active').first()

    if not session:
        return Response({'error': 'No active game session'}, status=status.HTTP_400_BAD_REQUEST)

    if session.cashout_balance <= 0:
        return Response({'error': 'Nothing to pause for'}, status=status.HTTP_400_BAD_REQUEST)

    config = GameConfig.objects.get(currency=session.currency)
    pause_cost = session.cashout_balance * (config.pause_cost_percent / Decimal('100'))
    pause_cost = pause_cost.quantize(Decimal('0.01'))

    serializer = PauseSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    if not serializer.validated_data['confirm']:
        # Just show the cost
        return Response({
            'pause_cost': str(pause_cost),
            'current_balance': str(session.cashout_balance),
            'balance_after_pause': str(session.cashout_balance - pause_cost),
            'message': f'Pausing will cost {session.currency.symbol}{pause_cost}. Send confirm=true to proceed.',
        })

    from wallet.models import Wallet, WalletTransaction

    with transaction.atomic():
        # Deduct pause fee from cashout balance
        session.cashout_balance -= pause_cost
        session.pause_fee_paid += pause_cost
        session.status = 'paused'
        session.save(update_fields=['cashout_balance', 'pause_fee_paid', 'status'])

        # Record pause fee transaction
        wallet = Wallet.objects.get(player=player)
        tx_ref = f'CF-PAUSE-{uuid.uuid4().hex[:8].upper()}'
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=-pause_cost,
            tx_type='pause_fee',
            reference=tx_ref,
            balance_before=wallet.balance,
            balance_after=wallet.balance,
            metadata={'session_id': str(session.id)},
        )

    return Response({
        'status': 'paused',
        'pause_cost': str(pause_cost),
        'remaining_balance': str(session.cashout_balance),
        'session_id': str(session.id),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resume_game(request):
    """Resume a paused game session."""
    player = request.user
    session = GameSession.objects.filter(player=player, status='paused').first()

    if not session:
        return Response({'error': 'No paused game session'}, status=status.HTTP_400_BAD_REQUEST)

    session.status = 'active'
    session.save(update_fields=['status'])

    return Response({
        'status': 'active',
        'cashout_balance': str(session.cashout_balance),
        'flip_count': session.flip_count,
        'session_id': str(session.id),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def game_state(request):
    """Get current game state (for reconnection)."""
    player = request.user
    session = GameSession.objects.filter(
        player=player, status__in=['active', 'paused']
    ).first()

    if not session:
        return Response({'active_session': False})

    return Response({
        'active_session': True,
        'session': GameSessionSerializer(session).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def game_history(request):
    """Get past game sessions."""
    player = request.user
    sessions = GameSession.objects.filter(player=player).exclude(
        status='active'
    ).order_by('-created_at')[:50]
    return Response(GameSessionListSerializer(sessions, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_session(request, session_id):
    """Verify provably fair results for a completed session."""
    try:
        session = GameSession.objects.get(id=session_id)
    except GameSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

    if session.status == 'active':
        return Response({'error': 'Session still active'}, status=status.HTTP_400_BAD_REQUEST)

    from game.engine import generate_result_hash, hash_to_float, calculate_zero_probability

    flips_data = []
    config = GameConfig.objects.get(currency=session.currency)

    for flip_obj in session.flips.all().order_by('flip_number'):
        expected_hash = generate_result_hash(session.server_seed, session.client_seed, flip_obj.flip_number)
        flips_data.append({
            'flip_number': flip_obj.flip_number,
            'value': str(flip_obj.value),
            'is_zero': flip_obj.is_zero,
            'result_hash': flip_obj.result_hash,
            'verified': flip_obj.result_hash == expected_hash,
        })

    return Response({
        'session_id': str(session.id),
        'server_seed': session.server_seed,
        'server_seed_hash': session.server_seed_hash,
        'client_seed': session.client_seed,
        'status': session.status,
        'stake_amount': str(session.stake_amount),
        'cashout_balance': str(session.cashout_balance),
        'flips': flips_data,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def live_feed(request):
    """
    Public live feed of recent game results (Aviator-style).
    Returns last 20 completed sessions with masked player names.
    No auth required — visible to everyone for credibility.
    Includes simulated entries when admin enables demo mode.
    """
    import random
    from datetime import timedelta

    sessions = GameSession.objects.filter(
        status__in=['cashed_out', 'lost']
    ).select_related('player', 'currency').order_by('-ended_at')[:20]

    def mask_name(player):
        name = player.display_name or player.get_display_name()
        if len(name) <= 3:
            return name[0] + '**'
        return name[:2] + '*' * (len(name) - 4) + name[-2:]

    feed = []
    for s in sessions:
        feed.append({
            'player': mask_name(s.player),
            'stake': str(s.stake_amount),
            'won': s.status == 'cashed_out',
            'amount': str(s.cashout_balance if s.status == 'cashed_out' else s.stake_amount),
            'flips': s.flip_count,
            'symbol': s.currency.symbol if s.currency else 'GH₵',
            'time': s.ended_at.isoformat() if s.ended_at else '',
        })

    # Merge simulated feed entries if demo mode is enabled
    try:
        config = GameConfig.objects.filter(is_active=True).first()
        if config and config.simulated_feed_enabled and config.simulated_feed_data:
            now = timezone.now()
            for i, item in enumerate(config.simulated_feed_data):
                sim_time = now - timedelta(seconds=random.randint(5, 300 + i * 30))
                sym = config.currency.symbol if config.currency else 'GH₵'
                feed.append({
                    'player': item.get('player', f'Pl**er{random.randint(10,99)}'),
                    'stake': item.get('stake', item.get('amount', '5.00')),
                    'won': item.get('won', random.choice([True, True, False])),
                    'amount': item.get('amount', '10.00'),
                    'flips': item.get('flips', random.randint(2, 8)),
                    'symbol': item.get('symbol', sym),
                    'time': sim_time.isoformat(),
                })
            # Sort by time descending and limit to 20
            feed.sort(key=lambda x: x.get('time', ''), reverse=True)
            feed = feed[:20]
    except Exception:
        pass

    return Response({'feed': feed})


# ==================== FEATURE CONFIG ====================

@extend_schema(tags=['Game: Features'], summary='Get Feature Config', description='Returns all global feature toggles (badges, wheel, sounds, haptics, etc.) for the frontend UI.')
@api_view(['GET'])
@permission_classes([AllowAny])
def feature_config(request):
    """Return global feature toggles for frontend."""
    fc = FeatureConfig.get_config()
    return Response({
        'badges_enabled': fc.badges_enabled,
        'daily_wheel_enabled': fc.daily_wheel_enabled,
        'sounds_enabled': fc.sounds_enabled,
        'haptics_enabled': fc.haptics_enabled,
        'social_proof_enabled': fc.social_proof_enabled,
        'streak_badge_enabled': fc.streak_badge_enabled,
        'confetti_enabled': fc.confetti_enabled,
        'deposit_sound_enabled': fc.deposit_sound_enabled,
        'social_proof_min_amount': str(fc.social_proof_min_amount),
    })


# ==================== BADGES ====================

@extend_schema(tags=['Game: Features'], summary='Get Player Badges', description='Returns all achievement badges with the current player\'s earned/locked status, total XP, and earned count.')
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def player_badges(request):
    """Return all badges with player's earned status."""
    all_badges = Badge.objects.filter(is_active=True)
    earned = set(PlayerBadge.objects.filter(player=request.user).values_list('badge__code', flat=True))

    result = []
    for b in all_badges:
        result.append({
            'code': b.code,
            'name': b.name,
            'description': b.description,
            'emoji': b.emoji,
            'xp': b.xp_value,
            'earned': b.code in earned,
        })
    total_xp = sum(b.xp_value for b in all_badges if b.code in earned)
    return Response({'badges': result, 'total_xp': total_xp, 'earned_count': len(earned)})


def check_and_award_badges(player, session=None, flip_data=None):
    """Check conditions and award badges. Called after flips/cashouts."""
    import random
    awarded = []

    def award(code):
        try:
            badge = Badge.objects.get(code=code, is_active=True)
            _, created = PlayerBadge.objects.get_or_create(
                player=player, badge=badge, defaults={'session': session}
            )
            if created:
                awarded.append({'code': code, 'name': badge.name, 'emoji': badge.emoji})
        except Badge.DoesNotExist:
            pass

    # First win
    if flip_data and not flip_data.get('is_zero'):
        if not PlayerBadge.objects.filter(player=player, badge__code='first_win').exists():
            award('first_win')

    # Streak badges (check consecutive wins in current session)
    if session and flip_data and not flip_data.get('is_zero'):
        flips = FlipResult.objects.filter(session=session).order_by('-flip_number')
        streak = 0
        for f in flips:
            if f.is_zero:
                break
            streak += 1
        if streak >= 3:
            award('streak_3')
        if streak >= 5:
            award('streak_5')
        if streak >= 7:
            award('streak_7')

    # Lucky 7 (won on flip #7)
    if flip_data and flip_data.get('flip_number') == 7 and not flip_data.get('is_zero'):
        award('lucky_7')

    # High roller / Whale
    if session:
        stake = float(session.stake_amount)
        if stake >= 100:
            award('high_roller')
        if stake >= 500:
            award('whale')

    # Cashout badges
    if flip_data and flip_data.get('cashout_amount'):
        ca = float(flip_data['cashout_amount'])
        if ca >= 50:
            award('big_cashout')
        if ca >= 200:
            award('mega_cashout')

    # Flip master (100 total flips)
    total_flips = FlipResult.objects.filter(session__player=player).count()
    if total_flips >= 100:
        award('flip_master')

    # Veteran (50 sessions)
    total_sessions = GameSession.objects.filter(player=player).count()
    if total_sessions >= 50:
        award('veteran')

    return awarded


# ==================== DAILY BONUS WHEEL ====================

@extend_schema(tags=['Game: Features'], summary='Daily Wheel Status', description='Check if the player can spin the daily bonus wheel. Returns availability, next spin time, and wheel segment configuration.')
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def daily_wheel_status(request):
    """Check if player can spin the daily wheel."""
    config = DailyBonusConfig.get_config()
    if not config or not config.is_enabled:
        return Response({'available': False, 'reason': 'Daily wheel is disabled'})

    now = timezone.now()
    last_spin = DailyBonusSpin.objects.filter(player=request.user).order_by('-spun_at').first()

    can_spin = True
    next_spin = None
    if last_spin:
        cooldown = timezone.timedelta(hours=config.cooldown_hours)
        next_spin_time = last_spin.spun_at + cooldown
        if now < next_spin_time:
            can_spin = False
            next_spin = next_spin_time.isoformat()

    if config.require_deposit:
        from payments.models import Deposit
        has_deposit = Deposit.objects.filter(player=request.user, status='completed').exists()
        if not has_deposit:
            can_spin = False

    return Response({
        'available': can_spin,
        'next_spin': next_spin,
        'segments': config.segments,
        'enabled': config.is_enabled,
    })


@extend_schema(tags=['Game: Features'], summary='Spin Daily Wheel', description='Spin the daily bonus wheel. Performs weighted random selection, credits the won amount to the player wallet, and returns the winning segment index for frontend animation.')
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def daily_wheel_spin(request):
    """Spin the daily bonus wheel and credit winnings."""
    import random as rng

    config = DailyBonusConfig.get_config()
    if not config or not config.is_enabled:
        return Response({'error': 'Daily wheel is disabled'}, status=status.HTTP_400_BAD_REQUEST)

    now = timezone.now()
    last_spin = DailyBonusSpin.objects.filter(player=request.user).order_by('-spun_at').first()
    if last_spin:
        cooldown = timezone.timedelta(hours=config.cooldown_hours)
        if now < last_spin.spun_at + cooldown:
            return Response({'error': 'Spin not available yet'}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    segments = config.segments
    if not segments:
        return Response({'error': 'No wheel segments configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Weighted random selection
    weights = [s.get('weight', 1) for s in segments]
    chosen = rng.choices(segments, weights=weights, k=1)[0]
    amount = Decimal(str(chosen['value']))

    # Credit wallet
    from wallet.models import Wallet, WalletTransaction
    try:
        with transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(player=request.user)
            before = wallet.balance
            wallet.balance += amount
            wallet.save(update_fields=['balance', 'updated_at'])
            WalletTransaction.objects.create(
                wallet=wallet, amount=amount, tx_type='ad_bonus',
                reference=f'WHEEL-{uuid.uuid4().hex[:12].upper()}',
                status='completed', balance_before=before, balance_after=wallet.balance,
                metadata={'type': 'daily_wheel', 'segment': chosen['label']},
            )
    except Wallet.DoesNotExist:
        return Response({'error': 'Wallet not found'}, status=status.HTTP_404_NOT_FOUND)

    DailyBonusSpin.objects.create(
        player=request.user, amount=amount, segment_label=chosen['label'],
    )

    # Index of chosen segment for frontend animation
    seg_index = segments.index(chosen)

    return Response({
        'success': True,
        'segment_index': seg_index,
        'label': chosen['label'],
        'amount': str(amount),
        'new_balance': str(wallet.balance),
    })
