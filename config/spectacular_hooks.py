"""
drf-spectacular preprocessing hooks.
"""


def preprocess_exclude_admin(endpoints, **kwargs):
    """Exclude admin dashboard API and internal endpoints from public API docs."""
    filtered = []
    for (path, path_regex, method, callback) in endpoints:
        # Exclude admin dashboard API
        if path.startswith('/api/admin/'):
            continue
        # Exclude Django admin
        if path.startswith('/admin/'):
            continue
        # Exclude internal endpoints
        if path in ('/health/',):
            continue
        # Exclude accounts (internal player auth)
        if path.startswith('/api/accounts/'):
            continue
        # Exclude payments (internal)
        if path.startswith('/api/payments/'):
            continue
        filtered.append((path, path_regex, method, callback))
    return filtered
