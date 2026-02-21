"""
Cashflip Game Engine — WYSIWYG Budget-Based Payout with Exponential Decay

"What You See Is What You Get" — the denomination note shown IS the
payout added to the player's cashout balance.

House edge is enforced via a per-session **payout budget**:
    payout_budget = stake × (payout_target / 100)

The budget is distributed across flips using exponential decay weights:
    weight_i = e^(-k × (i - 1))

When the remaining budget cannot cover the smallest denomination,
the player hits the ZERO note and the session ends.

Holiday Trigger: 1-in-N low-stake players get a boosted payout
percentage for engagement.
"""

import hashlib
import math
import random
import secrets
import logging
from decimal import Decimal, ROUND_DOWN

from django.utils import timezone

from game.models import (
    Currency, CurrencyDenomination, GameConfig,
    SimulatedGameConfig, GameSession, FlipResult, StakeTier,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provably fair primitives
# ---------------------------------------------------------------------------

def generate_result_hash(server_seed, client_seed, nonce):
    """Generate provably fair result hash."""
    message = f'{server_seed}:{client_seed}:{nonce}'
    return hashlib.sha256(message.encode()).hexdigest()


def hash_to_float(result_hash):
    """Convert hash to float between 0 and 1."""
    hex_value = result_hash[:8]
    int_value = int(hex_value, 16)
    return int_value / 0xFFFFFFFF


# ---------------------------------------------------------------------------
# Stake tier helpers
# ---------------------------------------------------------------------------

def resolve_stake_tier(currency, stake_amount):
    """Find the StakeTier matching the given stake amount."""
    if not stake_amount:
        return None
    try:
        return StakeTier.objects.filter(
            currency=currency,
            is_active=True,
            min_stake__lte=stake_amount,
            max_stake__gte=stake_amount,
        ).first()
    except Exception:
        return None


def get_tier_denominations(currency, stake_amount):
    """
    Return the list of non-zero active denominations for the player's tier,
    sorted by value ascending.
    """
    tier = resolve_stake_tier(currency, stake_amount)
    if tier:
        denoms = list(tier.denominations.filter(
            is_zero=False, is_active=True
        ).order_by('value'))
        if denoms:
            return denoms
    # Fallback: all active non-zero denominations
    return list(CurrencyDenomination.objects.filter(
        currency=currency, is_zero=False, is_active=True
    ).order_by('value'))


# ---------------------------------------------------------------------------
# Exponential decay weights
# ---------------------------------------------------------------------------

def compute_decay_weights(k, max_flips):
    """
    Compute normalised exponential decay weights for up to max_flips.

        weight_i = e^(-k × (i - 1))   (i is 1-indexed)
        normalised_weight_i = weight_i / sum(weights)

    Returns list of floats that sum to 1.0.
    """
    raw = [math.exp(-k * (i - 1)) for i in range(1, max_flips + 1)]
    total = sum(raw)
    if total == 0:
        return [1.0 / max_flips] * max_flips
    return [w / total for w in raw]


def compute_payout_schedule(k, max_flips, payout_budget):
    """
    Compute the ideal payout per flip position.
    Returns list of Decimal amounts.
    """
    weights = compute_decay_weights(k, max_flips)
    budget_float = float(payout_budget)
    return [
        Decimal(str(round(w * budget_float, 2)))
        for w in weights
    ]


# ---------------------------------------------------------------------------
# Holiday trigger
# ---------------------------------------------------------------------------

def check_holiday_boost(config, currency, stake_amount):
    """
    Determine if this session should receive the holiday boost.
    Returns (is_boosted, effective_payout_pct).
    """
    if not config.holiday_mode_enabled:
        pct = _effective_payout_pct(config)
        return False, pct

    # Only boost players in qualifying tiers
    tier = resolve_stake_tier(currency, stake_amount)
    if config.holiday_max_tier_name:
        qualifying = StakeTier.objects.filter(
            currency=currency, is_active=True,
            name__iexact=config.holiday_max_tier_name,
        ).first()
        if qualifying and tier and tier.min_stake > qualifying.max_stake:
            # Player is in a higher tier — no boost
            pct = _effective_payout_pct(config)
            return False, pct

    # Roll dice: 1 in N chance
    freq = max(config.holiday_frequency, 1)
    if random.randint(1, freq) == 1:
        logger.info(f'[HOLIDAY] Player boosted! payout={config.holiday_boost_pct}%')
        return True, config.holiday_boost_pct

    pct = _effective_payout_pct(config)
    return False, pct


def _effective_payout_pct(config):
    """Return the effective payout percentage based on payout_mode."""
    if config.payout_mode == 'boost':
        return config.boost_payout_target
    return config.normal_payout_target


# ---------------------------------------------------------------------------
# Session initialisation (called from views.start_game)
# ---------------------------------------------------------------------------

def initialise_session_budget(session, config):
    """
    Calculate and store the payout budget for a new session.
    Must be called right after session creation.
    """
    is_boosted, payout_pct = check_holiday_boost(
        config, session.currency, session.stake_amount
    )
    budget = (session.stake_amount * payout_pct / Decimal('100')).quantize(
        Decimal('0.01'), rounding=ROUND_DOWN
    )
    session.payout_budget = budget
    session.remaining_budget = budget
    session.payout_pct_used = payout_pct
    session.is_holiday_boosted = is_boosted
    session.save(update_fields=[
        'payout_budget', 'remaining_budget',
        'payout_pct_used', 'is_holiday_boosted',
    ])
    return budget


# ---------------------------------------------------------------------------
# Denomination selection — WYSIWYG (face value = payout)
# ---------------------------------------------------------------------------

def select_denomination_wysiwyg(session, config, result_hash):
    """
    Select a denomination whose face value fits within the remaining budget,
    guided by the exponential decay target for this flip position.

    Logic:
    1. Compute the target payout for this flip using decay weights.
    2. Filter denominations whose face value ≤ remaining_budget.
    3. Pick the denomination closest to the target.
    4. If no denomination fits → return zero.

    Returns (denomination, face_value_as_decimal, is_zero).
    """
    remaining = session.remaining_budget
    flip_number = session.flip_count  # Already incremented before calling this

    # Get available denominations for this tier
    denoms = get_tier_denominations(session.currency, session.stake_amount)

    # Filter to only those that fit in remaining budget
    affordable = [d for d in denoms if d.value <= remaining]

    if not affordable:
        # ZERO — budget exhausted
        zero_denom = CurrencyDenomination.objects.filter(
            currency=session.currency, is_zero=True, is_active=True
        ).first()
        return zero_denom, Decimal('0.00'), True

    # Compute target payout for this flip position
    k = float(config.decay_factor)
    max_flips = config.max_flips_per_session
    target_payouts = compute_payout_schedule(k, max_flips, session.payout_budget)

    # Get target for current flip (clamped to schedule length)
    idx = min(flip_number - 1, len(target_payouts) - 1)
    target = float(target_payouts[idx])

    # Use provably fair hash to add controlled randomness to selection
    roll = hash_to_float(result_hash[8:16])

    # Sort affordable by closeness to target
    affordable.sort(key=lambda d: abs(float(d.value) - target))

    # Pick from top candidates using the roll for randomness
    # Take the 3 closest denominations (or fewer if not available)
    candidates = affordable[:min(3, len(affordable))]

    # Weighted selection: closer to target = higher probability
    if len(candidates) == 1:
        selected = candidates[0]
    else:
        # Weight inversely proportional to distance from target (+1 to avoid /0)
        distances = [abs(float(c.value) - target) + 0.01 for c in candidates]
        inv_weights = [1.0 / d for d in distances]
        total_w = sum(inv_weights)
        normalised = [w / total_w for w in inv_weights]

        # Use the roll to pick
        cumulative = 0.0
        selected = candidates[-1]
        for i, cand in enumerate(candidates):
            cumulative += normalised[i]
            if roll <= cumulative:
                selected = cand
                break

    # Belt-and-suspenders: ensure selected denomination fits remaining budget
    if selected.value > remaining:
        # Shouldn't happen (affordable filter), but guard against it
        cheaper = [d for d in affordable if d.value <= remaining]
        if cheaper:
            selected = min(cheaper, key=lambda d: abs(float(d.value) - target))
        else:
            zero_denom = CurrencyDenomination.objects.filter(
                currency=session.currency, is_zero=True, is_active=True
            ).first()
            return zero_denom, Decimal('0.00'), True

    return selected, selected.value, False


# ---------------------------------------------------------------------------
# Simulation override (for testing/demo)
# ---------------------------------------------------------------------------

def get_simulated_outcome(session, flip_number, roll):
    """
    Check if a SimulatedGameConfig overrides the normal flip outcome.
    Returns (is_zero, forced_denom_value) or None if no simulation active.
    """
    sim = SimulatedGameConfig.get_active_config()
    if not sim or not sim.applies_to_player(session.player):
        return None

    mode = sim.outcome_mode
    forced_denom_value = sim.force_denomination_value

    if mode == 'normal':
        return None
    elif mode == 'always_win':
        return (False, forced_denom_value)
    elif mode == 'always_lose':
        return (True, None)
    elif mode == 'force_zero_at':
        if flip_number == sim.force_zero_at_flip:
            return (True, None)
        return (False, forced_denom_value)
    elif mode == 'fixed_probability':
        prob = float(sim.fixed_zero_probability)
        is_zero = roll < prob
        return (is_zero, forced_denom_value if not is_zero else None)
    elif mode == 'streak_then_lose':
        if flip_number <= sim.win_streak_length:
            return (False, forced_denom_value)
        return (True, None)
    return None


# ---------------------------------------------------------------------------
# Core flip execution
# ---------------------------------------------------------------------------

def execute_flip(session):
    """
    Execute a single WYSIWYG flip for a game session.

    The denomination shown IS the amount added to cashout_balance.
    House edge is enforced via the payout budget, not via multipliers.

    Returns dict with flip result data for the API response.
    """
    try:
        config = GameConfig.objects.get(currency=session.currency, is_active=True)
    except GameConfig.DoesNotExist:
        return {'success': False, 'error': 'Game configuration not found'}

    # Check max flips
    if session.flip_count >= config.max_flips_per_session:
        return {'success': False, 'error': 'Maximum flips reached for this session'}

    # Increment nonce and flip count
    session.nonce += 1
    session.flip_count += 1
    flip_number = session.flip_count

    # Generate provably fair result
    result_hash = generate_result_hash(
        session.server_seed, session.client_seed, session.nonce
    )
    roll = hash_to_float(result_hash)

    # Check simulation override first
    simulated = get_simulated_outcome(session, flip_number, roll)

    if simulated is not None:
        sim_is_zero, sim_forced_value = simulated
        logger.info(
            f'[SIM] session={session.id} flip={flip_number} '
            f'override -> is_zero={sim_is_zero}'
        )
        if sim_is_zero:
            denomination, value, is_zero = _get_zero_denom(session), Decimal('0.00'), True
        elif sim_forced_value is not None:
            # Force a specific denomination
            forced = CurrencyDenomination.objects.filter(
                currency=session.currency,
                value=sim_forced_value,
                is_active=True, is_zero=False,
            ).first()
            if forced and forced.value <= session.remaining_budget:
                denomination, value, is_zero = forced, forced.value, False
            else:
                denomination, value, is_zero = select_denomination_wysiwyg(
                    session, config, result_hash
                )
        else:
            denomination, value, is_zero = select_denomination_wysiwyg(
                session, config, result_hash
            )
    else:
        # Normal WYSIWYG selection (budget-driven, no separate zero curve)
        denomination, value, is_zero = select_denomination_wysiwyg(
            session, config, result_hash
        )

    # Apply result
    actual_payout = Decimal('0.00')
    if is_zero:
        session.cashout_balance = Decimal('0.00')
        session.remaining_budget = Decimal('0.00')
        session.status = 'lost'
        session.ended_at = timezone.now()
    else:
        # Guard: never let remaining_budget go negative
        actual_payout = min(value, session.remaining_budget)
        session.cashout_balance += actual_payout
        session.remaining_budget -= actual_payout
        if session.remaining_budget < Decimal('0'):
            session.remaining_budget = Decimal('0.00')
        # Enforce max_cashout cap
        if config.max_cashout and session.cashout_balance > config.max_cashout:
            session.cashout_balance = config.max_cashout
        # Log if actual_payout differs from denomination value (shouldn't happen)
        if actual_payout != value:
            logger.warning(
                f'WYSIWYG payout mismatch: session={session.id} flip={flip_number} '
                f'denom_value={value} actual_payout={actual_payout} remaining={session.remaining_budget}'
            )

    session.save(update_fields=[
        'nonce', 'flip_count', 'cashout_balance',
        'remaining_budget', 'status', 'ended_at',
    ])

    # Record flip result (use actual_payout as the recorded value for WYSIWYG accuracy)
    FlipResult.objects.create(
        session=session,
        flip_number=flip_number,
        denomination=denomination,
        value=actual_payout,
        is_zero=is_zero,
        cumulative_balance=session.cashout_balance,
        result_hash=result_hash,
    )

    # Check if ad should be shown
    ad_due = False
    try:
        from ads.models import AdConfig
        ad_config = AdConfig.get_config()
        if ad_config.ads_enabled and flip_number % ad_config.show_every_n_flips == 0:
            ad_due = True
    except Exception:
        pass

    result = {
        'success': True,
        'is_zero': is_zero,
        'value': str(actual_payout),
        'cashout_balance': str(session.cashout_balance),
        'remaining_budget': str(session.remaining_budget),
        'flip_number': flip_number,
        'result_hash': result_hash,
        'ad_due': ad_due,
        'is_holiday_boosted': session.is_holiday_boosted,
    }

    if denomination:
        # Upload fields take priority over static paths (matching serializer logic)
        face_path = denomination.face_image_upload.url if denomination.face_image_upload else (denomination.face_image_path or None)
        gif_path = denomination.flip_gif_upload.url if denomination.flip_gif_upload else (denomination.flip_gif_path or None)
        result['denomination'] = {
            'value': str(denomination.value),
            'is_zero': denomination.is_zero,
            'front_image_url': denomination.front_image.url if denomination.front_image else None,
            'back_image_url': denomination.back_image.url if denomination.back_image else None,
            'face_image_path': face_path,
            'flip_sequence_prefix': denomination.flip_sequence_prefix or None,
            'flip_sequence_frames': denomination.flip_sequence_frames,
            'flip_gif_path': gif_path,
            'flip_video_path': denomination.flip_video_path or None,
        }
    else:
        # No denomination found (e.g. zero denom not configured) — create minimal data
        logger.warning(f'No denomination object for session={session.id} flip={flip_number} is_zero={is_zero}')
        result['denomination'] = {
            'value': str(value),
            'is_zero': is_zero,
            'front_image_url': None,
            'back_image_url': None,
            'face_image_path': None,
            'flip_sequence_prefix': None,
            'flip_sequence_frames': 0,
            'flip_gif_path': None,
            'flip_video_path': None,
        }

    return result


def _get_zero_denom(session):
    """Helper to fetch the zero denomination."""
    return CurrencyDenomination.objects.filter(
        currency=session.currency, is_zero=True, is_active=True
    ).first()
