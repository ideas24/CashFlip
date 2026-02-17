"""
Seed initial data: GHS currency, denominations, game config, admin roles
"""

from django.core.management.base import BaseCommand
from game.models import Currency, CurrencyDenomination, GameConfig
from accounts.models import AdminRole
from ads.models import AdConfig
from referrals.models import ReferralConfig


class Command(BaseCommand):
    help = 'Seed initial Cashflip data'

    def handle(self, *args, **options):
        # Create GHS currency
        ghs, created = Currency.objects.get_or_create(
            code='GHS',
            defaults={'name': 'Ghana Cedi', 'symbol': 'GH₵', 'is_default': True}
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created GHS currency'))

        # Create denominations (with placeholder images - upload real ones via admin)
        denominations = [
            {'value': 0, 'display_order': 0, 'is_zero': True, 'weight': 0},
            {'value': 1, 'display_order': 1, 'is_zero': False, 'weight': 30},
            {'value': 2, 'display_order': 2, 'is_zero': False, 'weight': 25},
            {'value': 5, 'display_order': 3, 'is_zero': False, 'weight': 20},
            {'value': 10, 'display_order': 4, 'is_zero': False, 'weight': 12},
            {'value': 20, 'display_order': 5, 'is_zero': False, 'weight': 8},
            {'value': 50, 'display_order': 6, 'is_zero': False, 'weight': 4},
            {'value': 100, 'display_order': 7, 'is_zero': False, 'weight': 1},
            {'value': 200, 'display_order': 8, 'is_zero': False, 'weight': 0.5},
        ]

        for d in denominations:
            obj, created = CurrencyDenomination.objects.get_or_create(
                currency=ghs,
                value=d['value'],
                defaults={
                    'display_order': d['display_order'],
                    'is_zero': d['is_zero'],
                    'weight': int(d['weight']) if d['weight'] >= 1 else 1,
                    'is_active': True,
                }
            )
            if created:
                label = 'ZERO' if d['is_zero'] else f"GH₵{d['value']}"
                self.stdout.write(f'  Created denomination: {label}')

        # Create game config
        config, created = GameConfig.objects.get_or_create(
            currency=ghs,
            defaults={
                'house_edge_percent': 60,
                'min_deposit': 1.00,
                'max_cashout': 10000.00,
                'min_stake': 1.00,
                'pause_cost_percent': 10.00,
                'zero_base_rate': 0.05,
                'zero_growth_rate': 0.08,
                'min_flips_before_zero': 2,
                'max_session_duration_minutes': 120,
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created GHS game config'))

        # Create admin roles
        roles = [
            {'name': 'Super Admin', 'codename': 'super_admin', 'permissions': ['super_admin']},
            {'name': 'Finance Manager', 'codename': 'finance_manager', 'permissions': ['view_financials', 'view_analytics']},
            {'name': 'Game Manager', 'codename': 'game_manager', 'permissions': ['manage_game_config', 'manage_currencies']},
            {'name': 'Marketing Manager', 'codename': 'marketing_manager', 'permissions': ['manage_ads', 'manage_referrals', 'view_analytics']},
            {'name': 'Support Agent', 'codename': 'support_agent', 'permissions': ['manage_players', 'view_financials']},
        ]

        for r in roles:
            obj, created = AdminRole.objects.get_or_create(
                codename=r['codename'],
                defaults={'name': r['name'], 'permissions': r['permissions']}
            )
            if created:
                self.stdout.write(f'  Created role: {r["name"]}')

        # Init singleton configs
        AdConfig.get_config()
        self.stdout.write('  Ad config initialized')

        ReferralConfig.get_config()
        self.stdout.write('  Referral config initialized')

        self.stdout.write(self.style.SUCCESS('\nSeed data complete!'))
