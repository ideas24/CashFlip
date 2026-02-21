"""
Management command to recalibrate payout_multiplier and weight values
for all CurrencyDenominations.

Target: 30% payout (70% house edge) in normal mode.
Boost mode auto-calculates from normal × boost_multiplier_factor.

Usage:
    python manage.py calibrate_multipliers          # Dry run (show changes)
    python manage.py calibrate_multipliers --apply   # Apply changes
"""

from decimal import Decimal
from django.core.management.base import BaseCommand
from game.models import CurrencyDenomination, GameConfig


# Target: weighted avg ~6% per flip × 5 expected flips = 30% payout = 70% house edge
# Boost: weighted avg ~8% per flip × 5 expected flips = 40% payout = 60% house edge
CALIBRATION = {
    # value: (normal_multiplier, boost_multiplier, weight)
    Decimal('1.00'):   (Decimal('3'),    Decimal('4'),    35),
    Decimal('2.00'):   (Decimal('4'),    Decimal('5.50'), 25),
    Decimal('5.00'):   (Decimal('5'),    Decimal('7'),    18),
    Decimal('10.00'):  (Decimal('7'),    Decimal('9'),    10),
    Decimal('20.00'):  (Decimal('10'),   Decimal('13'),   6),
    Decimal('50.00'):  (Decimal('18'),   Decimal('24'),   4),
    Decimal('100.00'): (Decimal('30'),   Decimal('40'),   2),
    Decimal('200.00'): (Decimal('50'),   Decimal('65'),   1),
}


class Command(BaseCommand):
    help = 'Recalibrate payout_multiplier and weight values for 70% house edge (30% payout)'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry run)')

    def handle(self, *args, **options):
        apply = options['apply']
        denoms = CurrencyDenomination.objects.filter(is_active=True).order_by('value')

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'{"APPLYING" if apply else "DRY RUN"}: Payout multiplier recalibration (70/30 target)'
        ))
        self.stdout.write(f'{"Value":<10} {"Old Mult":<10} {"New Mult":<10} {"Boost":<10} {"Old Wt":<8} {"New Wt":<8}')
        self.stdout.write('-' * 62)

        changed = 0
        total_weight = 0
        weighted_mult_normal = 0
        weighted_mult_boost = 0

        for d in denoms:
            if d.is_zero:
                self.stdout.write(f'{d.value:<10} {"(zero)":<10} {"(skip)":<10} {"—":<10} {d.weight:<8} {"—":<8}')
                continue

            cal = CALIBRATION.get(d.value)
            if not cal:
                self.stdout.write(self.style.WARNING(
                    f'{d.value:<10} {"?":<10} {"NOT FOUND":<10} {"—":<10} {d.weight:<8} {"—":<8}'
                ))
                continue

            new_mult, new_boost, new_weight = cal
            old_mult = d.payout_multiplier
            old_weight = d.weight

            marker = ''
            if old_mult != new_mult or old_weight != new_weight or d.boost_payout_multiplier != new_boost:
                marker = ' ← changed'
                changed += 1

            self.stdout.write(
                f'{d.value:<10} {old_mult:<10} {new_mult:<10} {new_boost:<10} {old_weight:<8} {new_weight:<8}{marker}'
            )

            total_weight += new_weight
            weighted_mult_normal += float(new_mult) * new_weight
            weighted_mult_boost += float(new_boost) * new_weight

            if apply and marker:
                d.payout_multiplier = new_mult
                d.boost_payout_multiplier = new_boost
                d.weight = new_weight
                d.save(update_fields=['payout_multiplier', 'boost_payout_multiplier', 'weight'])

        self.stdout.write('-' * 62)
        if total_weight > 0:
            avg_normal = weighted_mult_normal / total_weight
            avg_boost = weighted_mult_boost / total_weight
            payout_normal = 5.0 * avg_normal / 100
            payout_boost = 5.0 * avg_boost / 100
            self.stdout.write(f'\nNORMAL MODE:')
            self.stdout.write(f'  Weighted avg multiplier: {avg_normal:.2f}%')
            self.stdout.write(f'  Expected payout (5 flips): {payout_normal*100:.1f}%')
            self.stdout.write(f'  House edge: {(1-payout_normal)*100:.1f}%')
            self.stdout.write(f'\nBOOST MODE:')
            self.stdout.write(f'  Weighted avg multiplier: {avg_boost:.2f}%')
            self.stdout.write(f'  Expected payout (5 flips): {payout_boost*100:.1f}%')
            self.stdout.write(f'  House edge: {(1-payout_boost)*100:.1f}%')

        # Also update GameConfig defaults if applying
        if apply:
            configs = GameConfig.objects.filter(is_active=True)
            for cfg in configs:
                cfg.house_edge_percent = Decimal('70.00')
                cfg.min_stake = Decimal('50.00')
                cfg.min_deposit = Decimal('50.00')
                cfg.normal_payout_target = Decimal('30.00')
                cfg.boost_payout_target = Decimal('40.00')
                cfg.save(update_fields=[
                    'house_edge_percent', 'min_stake', 'min_deposit',
                    'normal_payout_target', 'boost_payout_target', 'updated_at'
                ])
                self.stdout.write(self.style.SUCCESS(f'\nGameConfig {cfg.currency.code}: house_edge=70%, min_stake=50, targets=30/40'))

            self.stdout.write(self.style.SUCCESS(f'\n{changed} denomination(s) updated.'))
        else:
            self.stdout.write(self.style.WARNING(f'\nDry run — {changed} change(s) pending. Use --apply to commit.'))
