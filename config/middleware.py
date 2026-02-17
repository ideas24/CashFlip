"""
Host-based admin access restriction.
Redirects /admin/ requests to the game homepage unless the request
arrives on the designated ADMIN_DOMAIN.
"""

from django.conf import settings
from django.http import HttpResponseRedirect


class AdminHostRestrictionMiddleware:
    """
    Block access to /admin/ on any host other than settings.ADMIN_DOMAIN.
    Players on the game subdomain will never see the admin login page —
    they get silently redirected to /.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_domain = getattr(settings, 'ADMIN_DOMAIN', '')

    def __call__(self, request):
        if self.admin_domain and request.path.startswith('/admin/'):
            host = request.get_host().split(':')[0]
            if host != self.admin_domain:
                return HttpResponseRedirect('/')
        return self.get_response(request)
