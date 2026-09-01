import time

from user.monitoring import observe_http_request


class ApiNoCacheMiddleware:
    """Force des en-têtes anti-cache pour les réponses API."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = time.perf_counter()
        response = None
        try:
            response = self.get_response(request)
            return response
        finally:
            duration = time.perf_counter() - started_at
            observe_http_request(request, response, duration)

            if response is not None and request.path.startswith('/api/'):
                response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
