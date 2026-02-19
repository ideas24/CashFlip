from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


def health_check(request):
    return JsonResponse({'status': 'ok', 'service': 'cashflip'})


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
    path('api/partner/v1/', include('partner.urls')),
    path('api/otp/v1/', include('partner.otp_urls')),
    path('api/admin/v1/', include('dashboard.urls')),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/docs/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # Social auth
    path('auth/', include('social_django.urls', namespace='social')),

    # Game UI (served as SPA)
    path('', TemplateView.as_view(template_name='game/index.html'), name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
