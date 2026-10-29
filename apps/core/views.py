from django.db import DatabaseError, connection
from django.http import HttpResponse


def healthz(request):
    """Liveness + DB reachability for load balancers and uptime monitors."""
    try:
        connection.ensure_connection()
    except DatabaseError:
        return HttpResponse("db unavailable", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
