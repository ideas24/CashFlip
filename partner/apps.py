from django.apps import AppConfig


class PartnerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'partner'

    def ready(self):
        import partner.schema  # noqa: F401 — registers OpenAPI auth extension
