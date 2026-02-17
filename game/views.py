"""
Game API Views - Start, Flip, Cashout, Pause, Resume, History, Verify
"""

import logging
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from game.engine import execute_flip
from game.models import Currency, CurrencyDenomination, GameConfig, SimulatedGameConfig, GameSession, FlipResult
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
    """Get game config for a currency."""
    code = request.query_params.get('currency', 'GHS')
    try:
        config = GameConfig.objects.select_related('currency').get(
            currency__code=code, is_active=True
        )
    except GameConfig.DoesNotExist:
        return Response({'error': 'Game config not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response(GameConfigPublicSerializer(config).data)


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

    # Check wallet balance
    from wallet.models import Wallet, WalletTransaction
    try:
        wallet = Wallet.objects.select_for_update().get(player=player)
    except Wallet.DoesNotExist:
        return Response({'error': 'Wallet not found. Please make a deposit first.'}, status=status.HTTP_400_BAD_REQUEST)

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

    if wallet.available_balance < stake_amount:
        return Response(
            {'error': f'Insufficient balance. Available: {currency.symbol}{wallet.available_balance}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    with transaction.atomic():
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

    result = execute_flip(session)

    if not result.get('success'):
        return Response({'error': result.get('error', 'Flip failed')}, status=status.HTTP_400_BAD_REQUEST)

    # If lost, unlock the stake (it's gone)
    if result['is_zero']:
        from wallet.models import Wallet
        try:
            wallet = Wallet.objects.get(player=player)
            wallet.locked_balance = max(Decimal('0'), wallet.locked_balance - session.stake_amount)
            wallet.save(update_fields=['locked_balance', 'updated_at'])
        except Wallet.DoesNotExist:
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

    return Response({
        'cashout_amount': str(cashout_amount),
        'new_balance': str(wallet.balance),
        'session_id': str(session.id),
    })


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
