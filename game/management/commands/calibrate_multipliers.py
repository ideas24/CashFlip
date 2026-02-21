"""
Management command to recalibrate payout_multiplier and weight values
for all CurrencyDenominations to achieve ~60% house edge.

Usage:
    python manage.py calibrate_multipliers          # Dry run (show changes)
    python manage.py calibrate_multipliers --apply   # Apply changes
"""

from decimal import Decimal
from django.core.management.base import BaseCommand
from game.models import CurrencyDenomination


# Target values from launch-readiness plan:
# Weighted avg mult = 8.45%, expected ~5 surviving flips → 42.25% payout → ~58% house edge
CALIBRATION = {
    # value: (new_multiplier, new_weight)
    Decimal('1.00'):   (Decimal('5'),  35),
    Decimal('2.00'):   (Decimal('7'),  25),
    Decimal('5.00'):   (Decimal('8'),  18),
    Decimal('10.00'):  (Decimal('10'), 10),
    Decimal('20.00'):  (Decimal('15'), 6),
    Decimal('50.00'):  (Decimal('25'), 4),
    Decimal('100.00'): (Decimal('40'), 2),
    Decimal('200.00'): (Decimal('60'), 1),
}


class Command(BaseCommand):
    help = 'Recalibrate payout_multiplier and weight values for ~60% house edge'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry run)')

    def handle(self, *args, **options):
        apply = options['apply']
        denoms = CurrencyDenomination.objects.filter(is_active=True).order_by('value')

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'{"APPLYING" if apply else "DRY RUN"}: Payout multiplier recalibration'
        ))
        self.stdout.write(f'{"Value":<10} {"Old Mult":<10} {"New Mult":<10} {"Old Wt":<8} {"New Wt":<8}')
        self.stdout.write('-' * 50)

        changed = 0
        total_weight = 0
        weighted_mult = 0

        for d in denoms:
            if d.is_zero:
                self.stdout.write(f'{d.value:<10} {"(zero)":<10} {"(skip)":<10} {d.weight:<8} {"—":<8}')
                continue

            cal = CALIBRATION.get(d.value)
            if not cal:
                self.stdout.write(self.style.WARNING(
                    f'{d.value:<10} {"?":<10} {"NOT FOUND":<10} {d.weight:<8} {"—":<8}'
                ))
                continue

            new_mult, new_weight = cal
            old_mult = d.payout_multiplier
            old_weight = d.weight

            marker = ''
            if old_mult != new_mult or old_weight != new_weight:
                marker = ' ← changed'
                changed += 1

            self.stdout.write(
                f'{d.value:<10} {old_mult:<10} {new_mult:<10} {old_weight:<8} {new_weight:<8}{marker}'
            )

            total_weight += new_weight
            weighted_mult += float(new_mult) * new_weight

            if apply and (old_mult != new_mult or old_weight != new_weight):
                d.payout_multiplier = new_mult
                d.weight = new_weight
                d.save(update_fields=['payout_multiplier', 'weight'])

        self.stdout.write('-' * 50)
        if total_weight > 0:
            avg_mult = weighted_mult / total_weight
            expected_payout = 5.0 * avg_mult / 100
            house_edge = 1.0 - expected_payout
            self.stdout.write(f'Weighted avg multiplier: {avg_mult:.2f}%')
            self.stdout.write(f'Expected payout (5 flips): {expected_payout*100:.1f}%')
            self.stdout.write(f'Estimated house edge: {house_edge*100:.1f}%')

        if apply:
            self.stdout.write(self.style.SUCCESS(f'\n{changed} denomination(s) updated.'))
        else:
            self.stdout.write(self.style.WARNING(f'\nDry run — {changed} change(s) pending. Use --apply to commit.'))
