"""
Seed default stake tiers for CashFlip.

Usage:
    python manage.py seed_stake_tiers
"""

from decimal import Decimal
from django.core.management.base import BaseCommand
from game.models import Currency, CurrencyDenomination, StakeTier


# Default tiers per management directive:
# 100 GHS stake → small notes (1,2,5)
# 1000 GHS stake → mid notes (10,20,50)
# 10000 GHS stake → large notes (50,100,200)
DEFAULT_TIERS = [
    {
        'name': 'Standard',
        'min_stake': Decimal('50'),
        'max_stake': Decimal('200'),
        'denom_values': [Decimal('1'), Decimal('2'), Decimal('5')],
        'display_order': 0,
    },
    {
        'name': 'Premium',
        'min_stake': Decimal('200.01'),
        'max_stake': Decimal('1000'),
        'denom_values': [Decimal('10'), Decimal('20'), Decimal('50')],
        'display_order': 1,
    },
    {
        'name': 'VIP',
        'min_stake': Decimal('1000.01'),
        'max_stake': Decimal('10000'),
        'denom_values': [Decimal('50'), Decimal('100'), Decimal('200')],
        'display_order': 2,
    },
]


class Command(BaseCommand):
    help = 'Seed default stake tiers (Standard, Premium, VIP)'

    def handle(self, *args, **options):
        currencies = Currency.objects.filter(is_active=True)
        if not currencies.exists():
            self.stdout.write(self.style.WARNING('No active currencies found. Create a currency first.'))
            return

        for currency in currencies:
            self.stdout.write(f'\nSeeding tiers for {currency.code}...')
            for tier_data in DEFAULT_TIERS:
                tier, created = StakeTier.objects.get_or_create(
                    currency=currency,
                    name=tier_data['name'],
                    defaults={
                        'min_stake': tier_data['min_stake'],
                        'max_stake': tier_data['max_stake'],
                        'display_order': tier_data['display_order'],
                        'is_active': True,
                    }
                )
                if not created:
                    tier.min_stake = tier_data['min_stake']
                    tier.max_stake = tier_data['max_stake']
                    tier.display_order = tier_data['display_order']
                    tier.save(update_fields=['min_stake', 'max_stake', 'display_order', 'updated_at'])

                # Link denominations
                denoms = CurrencyDenomination.objects.filter(
                    currency=currency,
                    value__in=tier_data['denom_values'],
                    is_active=True,
                    is_zero=False,
                )
                tier.denominations.set(denoms)
                denom_names = ', '.join(str(d.value) for d in denoms)
                status_label = 'created' if created else 'updated'
                self.stdout.write(self.style.SUCCESS(
                    f'  {tier.name} ({tier.min_stake}-{tier.max_stake}): [{denom_names}] — {status_label}'
                ))

        self.stdout.write(self.style.SUCCESS('\nStake tiers seeded successfully.'))
