"""
Partner API v1 — Views for operator integration.

All endpoints use PartnerHMACAuthentication.
request.user = Operator instance, request.auth = OperatorAPIKey instance.
"""

import uuid
import logging
from decimal import Decimal

from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from partner.auth import PartnerHMACAuthentication
from partner.models import (
    Operator, OperatorPlayer, OperatorSession, OperatorTransaction,
    OperatorGameConfig, OperatorWebhookConfig, OperatorSettlement,
)
from partner.serializers import (
    PlayerAuthSerializer, GameLaunchSerializer, GameStartSerializer,
    GameFlipSerializer, GameCashoutSerializer, GameStateSerializer,
    FlipResultSerializer, GameHistorySerializer, OperatorGameConfigSerializer,
    GGRReportSerializer, WebhookConfigureSerializer,
)
from partner.wallet_service import call_operator_debit, call_operator_credit, call_operator_rollback
from partner.webhooks import dispatch_webhook

from accounts.models import Player
from game.models import Currency, GameSession, FlipResult
from game.engine import execute_flip

logger = logging.getLogger(__name__)

PARTNER_AUTH = [PartnerHMACAuthentication]
PARTNER_PERMS = [AllowAny]  # Auth is handled by HMAC, not DRF permissions


def _get_operator(request):
    """Extract operator from HMAC-authenticated request."""
    if not isinstance(request.user, Operator):
        return None
    return request.user


# ==================== PLAYER MANAGEMENT ====================

@extend_schema(
    tags=['Partner: Players'],
    summary='Register / Authenticate Player',
    description='Register a new player or authenticate an existing one. Returns the internal player ID mapped to your external player ID. Call this before starting any game session.',
    responses={200: OpenApiResponse(description='Existing player found'), 201: OpenApiResponse(description='New player created')},
)
@api_view(['POST'])
@authentication_classes(PARTNER_AUTH)
@permission_classes(PARTNER_PERMS)
def player_auth(request):
    """Register or authenticate an operator's player."""
    operator = _get_operator(request)
    if not operator:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    serializer = PlayerAuthSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    ext_id = serializer.validated_data['ext_player_id']
    display_name = serializer.validated_data.get('display_name', '')

    # Find or create mapping
    op_player = OperatorPlayer.objects.filter(
        operator=operator, ext_player_id=ext_id
    ).select_related('player').first()

    if op_player:
        if display_name and display_name != op_player.display_name:
            op_player.display_name = display_name
            op_player.save(update_fields=['display_name'])
        return Response({
            'player_id': str(op_player.id),
            'ext_player_id': ext_id,
            'display_name': op_player.display_name,
            'created': False,
        })

    # Create internal player + mapping
    internal_phone = f'partner_{operator.slug}_{ext_id}'
    player, _ = Player.objects.get_or_create(
        phone=internal_phone,
        defaults={'display_name': display_name or f'{operator.name} Player'}
    )

    op_player = OperatorPlayer.objects.create(
        operator=operator,
        ext_player_id=ext_id,
        player=player,
        display_name=display_name,
    )

    return Response({
        'player_id': str(op_player.id),
        'ext_player_id': ext_id,
        'display_name': op_player.display_name,
        'created': True,
    }, status=status.HTTP_201_CREATED)


# ==================== GAME CONFIG ====================

@extend_schema(
    tags=['Partner: Game Config'],
    summary='Get Game Configuration',
    description='Retrieve your operator-specific game configuration including currency, house edge, stake limits, zero probability parameters, and session settings.',
)
@api_view(['GET'])
@authentication_classes(PARTNER_AUTH)
@permission_classes(PARTNER_PERMS)
def game_config(request):
    """Get operator's game configuration."""
    operator = _get_operator(request)
    if not operator:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        config = OperatorGameConfig.objects.select_related('currency').get(
            operator=operator, is_active=True
        )
    except OperatorGameConfig.DoesNotExist:
        return Response({'error': 'No game configuration found for this operator'},
                        status=status.HTTP_404_NOT_FOUND)

    return Response(OperatorGameConfigSerializer(config).data)


# ==================== GAME OPERATIONS ====================

@extend_schema(
    tags=['Partner: Game Operations'],
    summary='Start Game Session',
    description=(
        'Start a new game session for a player.\n\n'
        '**Flow**: Validate stake → call your debit_url to deduct stake → create session → return session ID + server seed hash.\n\n'
        '**Seamless Wallet**: Your debit endpoint is called synchronously. If debit fails, no session is created.\n\n'
        '**Provably Fair**: The `server_seed_hash` (SHA-256) is provided upfront. Full seed revealed after game ends.'
    ),
    responses={
        201: OpenApiResponse(description='Session created successfully'),
        400: OpenApiResponse(description='Invalid stake or missing config'),
        402: OpenApiResponse(description='Debit failed (insufficient funds on operator side)'),
        404: OpenApiResponse(description='Player not found'),
    },
)
@api_view(['POST'])
@authentication_classes(PARTNER_AUTH)
@permission_classes(PARTNER_PERMS)
def game_start(request):
    """Start a new game session."""
    operator = _get_operator(request)
    if not operator:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    serializer = GameStartSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    ext_id = serializer.validated_data['ext_player_id']
    stake = serializer.validated_data['stake']
    currency_code = serializer.validated_data['currency']
    client_seed = serializer.validated_data.get('client_seed', '')
    ext_session_ref = serializer.validated_data.get('ext_session_ref', '')

    # Resolve player
    try:
        op_player = OperatorPlayer.objects.select_related('player').get(
            operator=operator, ext_player_id=ext_id, is_active=True
        )
    except OperatorPlayer.DoesNotExist:
        return Response({'error': 'Player not found. Call players/auth first.'},
                        status=status.HTTP_404_NOT_FOUND)

    # Resolve config
    try:
        config = OperatorGameConfig.objects.select_related('currency').get(
            operator=operator, is_active=True
        )
    except OperatorGameConfig.DoesNotExist:
        return Response({'error': 'No game config for this operator'},
                        status=status.HTTP_400_BAD_REQUEST)

    # Validate stake
    if stake < config.min_stake:
        return Response({'error': f'Minimum stake is {config.min_stake}'},
                        status=status.HTTP_400_BAD_REQUEST)
    if stake > config.max_stake:
        return Response({'error': f'Maximum stake is {config.max_stake}'},
                        status=status.HTTP_400_BAD_REQUEST)

    # Call operator debit (synchronous for immediate feedback)
    debit_tx = call_operator_debit(
        operator, op_player, stake, currency_code, ext_session_ref
    )

    if debit_tx.status != 'success':
        return Response({
            'error': 'Debit failed',
            'detail': debit_tx.error_message,
            'tx_ref': debit_tx.tx_ref,
        }, status=status.HTTP_402_PAYMENT_REQUIRED)

    # Create game session
    try:
        session = GameSession.objects.create(
            player=op_player.player,
            currency=config.currency,
            stake_amount=stake,
            client_seed=client_seed or uuid.uuid4().hex[:16],
        )
        session.generate_seeds()

        op_session = OperatorSession.objects.create(
            operator=operator,
            operator_player=op_player,
            game_session=session,
            ext_session_ref=ext_session_ref,
            debit_tx_ref=debit_tx.tx_ref,
        )

        # Link transaction to session
        debit_tx.operator_session = op_session
        debit_tx.save(update_fields=['operator_session'])

        dispatch_webhook(operator, 'game.started', {
            'session_id': str(session.id),
            'ext_player_id': ext_id,
            'stake': str(stake),
            'currency': currency_code,
            'ext_session_ref': ext_session_ref,
        })

        return Response({
            'session_id': str(session.id),
            'server_seed_hash': session.server_seed_hash,
            'stake': str(stake),
            'currency': currency_code,
            'status': 'active',
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        # Rollback debit if session creation fails
        logger.error(f'Session creation failed after debit: {e}')
        call_operator_rollback(operator, op_player, stake, currency_code, debit_tx.tx_ref)
        return Response({'error': 'Session creation failed, debit rolled back'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['Partner: Game Operations'],
    summary='Execute Flip',
    description=(
        'Execute a single flip in an active game session.\n\n'
        '**Outcome**: Either a winning denomination value or zero (loss). '
        'Zero probability increases with each flip according to the configured escalation curve.\n\n'
        '**On Loss**: Session status changes to `lost`. The stake is forfeited.\n\n'
        '**On Win**: `cashout_balance` increases. Player can flip again or cash out.'
    ),
)
@api_view(['POST'])
@authentication_classes(PARTNER_AUTH)
@permission_classes(PARTNER_PERMS)
def game_flip(request):
    """Execute a flip for an active session."""
    operator = _get_operator(request)
    if not operator:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    serializer = GameFlipSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    session_id = serializer.validated_data['session_id']

    # Verify session belongs to this operator
    try:
        op_session = OperatorSession.objects.select_related(
            'game_session', 'operator_player'
        ).get(operator=operator, game_session_id=session_id)
    except OperatorSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

    session = op_session.game_session
    if session.status != 'active':
        return Response({'error': f'Session is {session.status}, not active'},
                        status=status.HTTP_400_BAD_REQUEST)

    # Execute flip using existing game engine
    result = execute_flip(session)

    if not result.get('success'):
        return Response({'error': result.get('error', 'Flip failed')},
                        status=status.HTTP_400_BAD_REQUEST)

    # Dispatch webhook
    webhook_event = 'game.lost' if result['is_zero'] else 'game.flip'
    dispatch_webhook(operator, webhook_event, {
        'session_id': str(session_id),
        'ext_player_id': op_session.operator_player.ext_player_id,
        'flip_number': result['flip_number'],
        'value': str(result['value']),
        'is_zero': result['is_zero'],
        'cashout_balance': str(result['cashout_balance']),
        'result_hash': result['result_hash'],
    })

    response_data = {
        'success': True,
        'flip_number': result['flip_number'],
        'value': str(result['value']),
        'is_zero': result['is_zero'],
        'cashout_balance': str(result['cashout_balance']),
        'result_hash': result['result_hash'],
        'session_status': session.status,
    }

    if result.get('denomination'):
        response_data['denomination'] = result['denomination']

    return Response(response_data)


@extend_schema(
    tags=['Partner: Game Operations'],
    summary='Cash Out Session',
    description=(
        'Cash out an active session and credit the player.\n\n'
        '**Flow**: Close session → call your credit_url with cashout amount → reveal server seed.\n\n'
        '**Seamless Wallet**: Your credit endpoint is called. Session is closed regardless of credit status '
        '(amount is owed to player).\n\n'
        '**Provably Fair**: The full `server_seed` is returned so the player can verify all flips.'
    ),
)
@api_view(['POST'])
@authentication_classes(PARTNER_AUTH)
@permission_classes(PARTNER_PERMS)
def game_cashout(request):
    """Cash out a session."""
    operator = _get_operator(request)
    if not operator:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    serializer = GameCashoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    session_id = serializer.validated_data['session_id']

    try:
        op_session = OperatorSession.objects.select_related(
            'game_session', 'operator_player'
        ).get(operator=operator, game_session_id=session_id)
    except OperatorSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

    session = op_session.game_session
    if session.status != 'active':
        return Response({'error': f'Session is {session.status}, not active'},
                        status=status.HTTP_400_BAD_REQUEST)

    cashout_amount = session.cashout_balance
    if cashout_amount <= 0:
        return Response({'error': 'Nothing to cash out'}, status=status.HTTP_400_BAD_REQUEST)

    # Credit operator wallet
    credit_tx = call_operator_credit(
        operator, op_session.operator_player, cashout_amount,
        session.currency.code, op_session.ext_session_ref
    )

    # Close session regardless of credit status (money is owed)
    session.status = 'cashed_out'
    session.ended_at = timezone.now()
    session.save(update_fields=['status', 'ended_at'])

    op_session.credit_tx_ref = credit_tx.tx_ref
    op_session.save(update_fields=['credit_tx_ref'])

    credit_tx.operator_session = op_session
    credit_tx.save(update_fields=['operator_session'])

    dispatch_webhook(operator, 'game.won', {
        'session_id': str(session_id),
        'ext_player_id': op_session.operator_player.ext_player_id,
        'cashout_amount': str(cashout_amount),
        'stake': str(session.stake_amount),
        'flips': session.flip_count,
        'credit_status': credit_tx.status,
        'credit_tx_ref': credit_tx.tx_ref,
    })

    return Response({
        'session_id': str(session_id),
        'cashout_amount': str(cashout_amount),
        'stake': str(session.stake_amount),
        'flips': session.flip_count,
        'status': 'cashed_out',
        'credit_status': credit_tx.status,
        'credit_tx_ref': credit_tx.tx_ref,
        'server_seed': session.server_seed,
    })


@extend_schema(
    tags=['Partner: Game Operations'],
    summary='Get Session State',
    description='Retrieve the current state of a game session including status, balances, flip count, and full flip history.',
)
@api_view(['GET'])
@authentication_classes(PARTNER_AUTH)
@permission_classes(PARTNER_PERMS)
def game_state(request, session_id):
    """Get current state of a session."""
    operator = _get_operator(request)
    if not operator:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        op_session = OperatorSession.objects.select_related(
            'game_session', 'operator_player'
        ).get(operator=operator, game_session_id=session_id)
    except OperatorSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

    data = GameStateSerializer(op_session).data

    # Include flip history
    flips = FlipResult.objects.filter(session=op_session.game_session).order_by('flip_number')
    data['flips'] = FlipResultSerializer(flips, many=True).data

    return Response(data)


@extend_schema(
    tags=['Partner: Game Operations'],
    summary='Get Player Game History',
    description='Retrieve the last 50 game sessions for a specific player, ordered by most recent first.',
)
@api_view(['GET'])
@authentication_classes(PARTNER_AUTH)
@permission_classes(PARTNER_PERMS)
def game_history(request, ext_player_id):
    """Get game history for an operator's player."""
    operator = _get_operator(request)
    if not operator:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    sessions = OperatorSession.objects.filter(
        operator=operator,
        operator_player__ext_player_id=ext_player_id,
    ).select_related('game_session').order_by('-created_at')[:50]

    return Response(GameHistorySerializer(sessions, many=True).data)


@extend_schema(
    tags=['Partner: Game Operations'],
    summary='Verify Session (Provably Fair)',
    description=(
        'Retrieve the full cryptographic verification data for a completed session.\n\n'
        '**Returns**: server_seed, server_seed_hash, client_seed, and all flip results with their hashes.\n\n'
        '**Verification**: For each flip, compute `HMAC-SHA256(server_seed, client_seed:nonce:flip_number)` '
        'and confirm it matches `result_hash`. The `server_seed_hash` = SHA-256(server_seed) should match '
        'the hash provided at game start.'
    ),
)
@api_view(['GET'])
@authentication_classes(PARTNER_AUTH)
@permission_classes(PARTNER_PERMS)
def game_verify(request, session_id):
    """Provably fair verification for a completed session."""
    operator = _get_operator(request)
    if not operator:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        op_session = OperatorSession.objects.select_related('game_session').get(
            operator=operator, game_session_id=session_id
        )
    except OperatorSession.DoesNotExist:
        return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

    session = op_session.game_session
    if session.status == 'active':
        return Response({'error': 'Cannot verify active sessions'},
                        status=status.HTTP_400_BAD_REQUEST)

    flips = FlipResult.objects.filter(session=session).order_by('flip_number')

    return Response({
        'session_id': str(session.id),
        'server_seed': session.server_seed,
        'server_seed_hash': session.server_seed_hash,
        'client_seed': session.client_seed,
        'nonce_start': 1,
        'total_flips': session.flip_count,
        'flips': FlipResultSerializer(flips, many=True).data,
    })


# ==================== REPORTS ====================

@extend_schema(
    tags=['Partner: Reports'],
    summary='GGR Report',
    description='Retrieve Gross Gaming Revenue reports showing total bets, total wins, GGR, commission, and net operator amount per settlement period.',
)
@api_view(['GET'])
@authentication_classes(PARTNER_AUTH)
@permission_classes(PARTNER_PERMS)
def reports_ggr(request):
    """GGR report — list settlements for operator."""
    operator = _get_operator(request)
    if not operator:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    settlements = OperatorSettlement.objects.filter(operator=operator).order_by('-period_end')[:50]
    return Response(GGRReportSerializer(settlements, many=True).data)


@extend_schema(
    tags=['Partner: Reports'],
    summary='Session Detail Report',
    description='Retrieve detailed session-level report for the last 100 sessions. Includes stake, cashout amount, flip count, status, and timestamps.',
    responses=GameHistorySerializer(many=True),
)
@api_view(['GET'])
@authentication_classes(PARTNER_AUTH)
@permission_classes(PARTNER_PERMS)
def reports_sessions(request):
    """Session-level detail report."""
    operator = _get_operator(request)
    if not operator:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    sessions = OperatorSession.objects.filter(
        operator=operator
    ).select_related('game_session', 'operator_player').order_by('-created_at')[:100]

    return Response(GameHistorySerializer(sessions, many=True).data)


@extend_schema(
    tags=['Partner: Settlements'],
    summary='List Settlements',
    description='Retrieve all settlement records for your operator account. Shows GGR, commission, net amount, and settlement status (pending/approved/paid).',
    responses=GGRReportSerializer(many=True),
)
@api_view(['GET'])
@authentication_classes(PARTNER_AUTH)
@permission_classes(PARTNER_PERMS)
def settlements_list(request):
    """List all settlements."""
    operator = _get_operator(request)
    if not operator:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    settlements = OperatorSettlement.objects.filter(operator=operator).order_by('-period_end')
    return Response(GGRReportSerializer(settlements, many=True).data)


# ==================== WEBHOOKS ====================

@extend_schema(
    tags=['Partner: Webhooks'],
    summary='Configure Webhooks',
    description=(
        'Set or update your webhook endpoint URL and subscribed events.\n\n'
        '**Supported events**: `game.started`, `game.flip`, `game.lost`, `game.won`, `settlement.generated`\n\n'
        'Cashflip will POST JSON payloads to your webhook URL for each subscribed event.'
    ),
    request=WebhookConfigureSerializer,
)
@api_view(['POST'])
@authentication_classes(PARTNER_AUTH)
@permission_classes(PARTNER_PERMS)
def webhooks_configure(request):
    """Configure webhook endpoint for operator."""
    operator = _get_operator(request)
    if not operator:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    serializer = WebhookConfigureSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    config, created = OperatorWebhookConfig.objects.update_or_create(
        operator=operator,
        defaults={
            'webhook_url': serializer.validated_data['webhook_url'],
            'subscribed_events': serializer.validated_data['subscribed_events'],
            'is_active': True,
        }
    )

    return Response({
        'webhook_url': config.webhook_url,
        'subscribed_events': config.subscribed_events,
        'is_active': config.is_active,
        'created': created,
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
