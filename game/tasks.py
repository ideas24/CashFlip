"""
Celery tasks for the game app.

- auto_flip_stale_sessions: Periodic task to auto-flip sessions that have been idle
  beyond the configured auto_flip_seconds threshold.
"""

import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(name='game.tasks.auto_flip_stale_sessions', bind=True, max_retries=0, ignore_result=True)
def auto_flip_stale_sessions(self):
    """
    Find active sessions where the last flip was longer ago than auto_flip_seconds,
    and execute a flip on each. This prevents players from holding sessions indefinitely.
    """
    from game.models import GameConfig, GameSession, FlipResult
    from game.engine import execute_flip

    configs = GameConfig.objects.filter(is_active=True, auto_flip_seconds__gt=0)
    total_flipped = 0

    for config in configs:
        threshold = timezone.now() - timedelta(seconds=config.auto_flip_seconds)

        # Find sessions that are active and haven't flipped recently
        stale_sessions = GameSession.objects.filter(
            status='active',
            currency=config.currency,
        ).select_related('player')

        for session in stale_sessions:
            # Check last flip time
            last_flip = FlipResult.objects.filter(session=session).order_by('-created_at').values_list('created_at', flat=True).first()
            last_activity = last_flip or session.created_at

            if last_activity > threshold:
                continue  # Not stale yet

            # Use Redis lock to prevent concurrent flips
            from django.core.cache import cache
            lock_key = f'flip_lock:{session.id}'
            if not cache.add(lock_key, 1, timeout=5):
                continue  # Already being flipped

            try:
                logger.info(f'Auto-flipping stale session {session.id} (player={session.player_id}, idle={int((timezone.now() - last_activity).total_seconds())}s)')
                result = execute_flip(session)
                total_flipped += 1

                if result.get('is_zero'):
                    logger.info(f'Auto-flip resulted in ZERO for session {session.id}')
                    # Release locked funds
                    from wallet.models import Wallet
                    from decimal import Decimal
                    from django.db import transaction
                    try:
                        with transaction.atomic():
                            wallet = Wallet.objects.select_for_update().get(player=session.player)
                            wallet.locked_balance = max(Decimal('0'), wallet.locked_balance - session.stake_amount)
                            wallet.save(update_fields=['locked_balance', 'updated_at'])
                    except Wallet.DoesNotExist:
                        pass
            except Exception as e:
                logger.error(f'Auto-flip failed for session {session.id}: {e}', exc_info=True)
            finally:
                cache.delete(lock_key)

    if total_flipped:
        logger.info(f'Auto-flip task completed: {total_flipped} session(s) flipped')
    return total_flipped
