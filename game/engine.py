"""
Cashflip Game Engine - Provably Fair Flip Logic

Server-authoritative game engine with configurable zero probability curve.
House edge target: 60% retention / 40% payout (configurable via GameConfig).
"""

import hashlib
import hmac
import math
import random
import secrets
import logging
from decimal import Decimal

from game.models import Currency, CurrencyDenomination, GameConfig, SimulatedGameConfig, GameSession, FlipResult

logger = logging.getLogger(__name__)


def generate_result_hash(server_seed, client_seed, nonce):
    """Generate provably fair result hash."""
    message = f'{server_seed}:{client_seed}:{nonce}'
    return hashlib.sha256(message.encode()).hexdigest()


def hash_to_float(result_hash):
    """Convert hash to float between 0 and 1."""
    # Use first 8 hex chars (32 bits) for uniform distribution
    hex_value = result_hash[:8]
    int_value = int(hex_value, 16)
    return int_value / 0xFFFFFFFF


def calculate_zero_probability(flip_number, config):
    """
    Calculate probability of zero (loss) for a given flip number.
    
    Formula: P(zero) = base_rate + (1 - base_rate) * (1 - e^(-k * (flip - min_flips)))
    For flip <= min_flips: P(zero) = 0 (guaranteed safe)
    
    This sigmoid-like curve ensures:
    - Early flips are safe (engagement hook)
    - Probability increases with each flip
    - Converges toward ~1.0 ensuring house edge over volume
    """
    min_flips = config.min_flips_before_zero
    
    if flip_number <= min_flips:
        return 0.0
    
    base_rate = float(config.zero_base_rate)
    k = float(config.zero_growth_rate)
    adjusted_flip = flip_number - min_flips
    
    probability = base_rate + (1 - base_rate) * (1 - math.exp(-k * adjusted_flip))
    return min(probability, 0.95)  # Cap at 95% to avoid guaranteed loss


def select_denomination(currency, result_hash, is_zero):
    """
    Select a denomination based on the result hash.
    If is_zero, return the zero denomination.
    Otherwise, weighted random selection from active denominations.
    """
    if is_zero:
        zero_denom = CurrencyDenomination.objects.filter(
            currency=currency, is_zero=True, is_active=True
        ).first()
        return zero_denom, Decimal('0.00')
    
    # Get non-zero active denominations
    denoms = list(CurrencyDenomination.objects.filter(
        currency=currency, is_zero=False, is_active=True
    ).order_by('value'))
    
    if not denoms:
        logger.error(f'No active denominations for {currency.code}')
        return None, Decimal('0.00')
    
    # Weighted random selection using result hash
    total_weight = sum(d.weight for d in denoms)
    hash_float = hash_to_float(result_hash[8:16])  # Use different portion of hash
    target = hash_float * total_weight
    
    cumulative = 0
    for denom in denoms:
        cumulative += denom.weight
        if target <= cumulative:
            return denom, denom.value
    
    # Fallback to last denomination
    return denoms[-1], denoms[-1].value


def get_simulated_outcome(session, flip_number, roll):
    """
    Check if a SimulatedGameConfig overrides the normal flip outcome.
    
    Returns:
        (is_zero, zero_prob, forced_denom_value) or None if no simulation active.
    """
    sim = SimulatedGameConfig.get_active_config()
    if not sim or not sim.applies_to_player(session.player):
        return None

    mode = sim.outcome_mode
    forced_denom_value = sim.force_denomination_value  # may be None

    if mode == 'normal':
        return None

    elif mode == 'always_win':
        return (False, 0.0, forced_denom_value)

    elif mode == 'always_lose':
        return (True, 1.0, None)

    elif mode == 'force_zero_at':
        if flip_number == sim.force_zero_at_flip:
            return (True, 1.0, None)
        return (False, 0.0, forced_denom_value)

    elif mode == 'fixed_probability':
        prob = float(sim.fixed_zero_probability)
        is_zero = roll < prob
        return (is_zero, prob, forced_denom_value if not is_zero else None)

    elif mode == 'streak_then_lose':
        if flip_number <= sim.win_streak_length:
            return (False, 0.0, forced_denom_value)
        return (True, 1.0, None)

    return None


def execute_flip(session):
    """
    Execute a single flip for a game session.
    
    Returns:
        dict: {
            'success': bool,
            'is_zero': bool,
            'denomination': {...} or None,
            'value': Decimal,
            'cashout_balance': Decimal,
            'flip_number': int,
            'result_hash': str,
            'ad_due': bool,  # Whether an ad should be shown
        }
    """
    try:
        config = GameConfig.objects.get(currency=session.currency, is_active=True)
    except GameConfig.DoesNotExist:
        return {'success': False, 'error': 'Game configuration not found'}
    
    # Increment nonce and flip count
    session.nonce += 1
    session.flip_count += 1
    flip_number = session.flip_count
    
    # Generate provably fair result
    result_hash = generate_result_hash(session.server_seed, session.client_seed, session.nonce)
    roll = hash_to_float(result_hash)
    
    # Check simulation override first
    simulated = get_simulated_outcome(session, flip_number, roll)
    if simulated is not None:
        is_zero, zero_prob, forced_denom_value = simulated
        logger.info(f'[SIM] session={session.id} flip={flip_number} mode override -> is_zero={is_zero}')
    else:
        # Normal probability curve
        zero_prob = calculate_zero_probability(flip_number, config)
        is_zero = roll < zero_prob
        forced_denom_value = None
    
    # Select denomination (with optional forced value from simulation)
    if forced_denom_value is not None and not is_zero:
        forced_denom = CurrencyDenomination.objects.filter(
            currency=session.currency, value=forced_denom_value, is_active=True
        ).first()
        if forced_denom:
            denomination, value = forced_denom, forced_denom.value
        else:
            denomination, value = select_denomination(session.currency, result_hash, is_zero)
    else:
        denomination, value = select_denomination(session.currency, result_hash, is_zero)
    
    if is_zero:
        # Player loses
        session.cashout_balance = Decimal('0.00')
        session.status = 'lost'
        session.ended_at = __import__('django.utils', fromlist=['timezone']).timezone.now()
    else:
        # Add denomination value to cashout balance
        session.cashout_balance += value
    
    session.save(update_fields=['nonce', 'flip_count', 'cashout_balance', 'status', 'ended_at'])
    
    # Record flip result
    flip = FlipResult.objects.create(
        session=session,
        flip_number=flip_number,
        denomination=denomination,
        value=value,
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
        'value': str(value),
        'cashout_balance': str(session.cashout_balance),
        'flip_number': flip_number,
        'result_hash': result_hash,
        'ad_due': ad_due,
        'zero_probability': round(zero_prob * 100, 1),
    }
    
    if denomination:
        result['denomination'] = {
            'value': str(denomination.value),
            'is_zero': denomination.is_zero,
            'image_url': denomination.banknote_image.url if denomination.banknote_image else None,
        }
    
    return result
