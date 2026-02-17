from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.generic import TemplateView


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

    # Social auth
    path('auth/', include('social_django.urls', namespace='social')),

    # Game UI (served as SPA)
    path('', TemplateView.as_view(template_name='game/index.html'), name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
