from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import TemplateView
from django.views.decorators.cache import never_cache
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from datetime import datetime


def health_check(request):
    return JsonResponse({'status': 'ok', 'service': 'cashflip'})


def privacy_policy_view(request):
    from game.models import LegalDocument
    legal = LegalDocument.get_legal()
    return render(request, 'game/legal.html', {
        'title': 'Privacy Policy',
        'doc_type': 'privacy',
        'content': legal.privacy_policy,
        'company_name': legal.company_name,
        'license_info': legal.license_info,
        'support_email': legal.support_email,
        'support_phone': legal.support_phone,
        'updated_at': legal.updated_at,
        'year': datetime.now().year,
    })


def terms_of_service_view(request):
    from game.models import LegalDocument
    legal = LegalDocument.get_legal()
    return render(request, 'game/legal.html', {
        'title': 'Terms of Service',
        'doc_type': 'terms',
        'content': legal.terms_of_service,
        'company_name': legal.company_name,
        'license_info': legal.license_info,
        'support_email': legal.support_email,
        'support_phone': legal.support_phone,
        'updated_at': legal.updated_at,
        'year': datetime.now().year,
    })


urlpatterns = [
    # Admin — access restricted to ADMIN_DOMAIN by AdminHostRestrictionMiddleware
    path('admin/', admin.site.urls),

    # Health check
    path('health/', health_check, name='health'),

    # API
    path('api/accounts/', include('accounts.urls')),
    path('api/game/', include('game.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/referrals/', include('referrals.urls')),
    path('api/vouchers/', include('vouchers.urls')),
    path('api/partner/v1/', include('partner.urls')),
    path('api/otp/v1/', include('partner.otp_urls')),
    path('api/admin/v1/', include('dashboard.urls')),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/docs/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # Social auth
    path('auth/', include('social_django.urls', namespace='social')),

    # Legal pages (public)
    path('privacy-policy/', privacy_policy_view, name='privacy_policy'),
    path('terms/', terms_of_service_view, name='terms_of_service'),

    # Game UI (served as SPA)
    path('', never_cache(TemplateView.as_view(template_name='game/index.html')), name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
