"""Seed default OTP pricing tiers."""

from django.db import migrations


def seed_pricing(apps, schema_editor):
    OTPPricingTier = apps.get_model('partner', 'OTPPricingTier')
    tiers = [
        {
            'name': 'Starter',
            'min_monthly_volume': 0,
            'max_monthly_volume': 5000,
            'price_per_otp_whatsapp': '0.0300',
            'price_per_otp_sms': '0.0500',
            'whitelabel_fee_monthly': '0.00',
            'whitelabel_available': False,
            'monthly_base_fee': '0.00',
            'priority_support': False,
            'sla_uptime': '99.00',
            'display_order': 1,
        },
        {
            'name': 'Growth',
            'min_monthly_volume': 5001,
            'max_monthly_volume': 50000,
            'price_per_otp_whatsapp': '0.0200',
            'price_per_otp_sms': '0.0350',
            'whitelabel_fee_monthly': '200.00',
            'whitelabel_available': True,
            'monthly_base_fee': '50.00',
            'priority_support': False,
            'sla_uptime': '99.50',
            'display_order': 2,
        },
        {
            'name': 'Business',
            'min_monthly_volume': 50001,
            'max_monthly_volume': 500000,
            'price_per_otp_whatsapp': '0.0120',
            'price_per_otp_sms': '0.0250',
            'whitelabel_fee_monthly': '500.00',
            'whitelabel_available': True,
            'monthly_base_fee': '200.00',
            'priority_support': True,
            'sla_uptime': '99.90',
            'display_order': 3,
        },
        {
            'name': 'Enterprise',
            'min_monthly_volume': 500001,
            'max_monthly_volume': 0,
            'price_per_otp_whatsapp': '0.0080',
            'price_per_otp_sms': '0.0150',
            'whitelabel_fee_monthly': '0.00',
            'whitelabel_available': True,
            'monthly_base_fee': '500.00',
            'priority_support': True,
            'sla_uptime': '99.99',
            'display_order': 4,
        },
    ]
    for t in tiers:
        OTPPricingTier.objects.get_or_create(name=t['name'], defaults=t)


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('partner', '0003_otppricingtier_otpclient_otpclientapikey_otpsenderid_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_pricing, reverse),
    ]
