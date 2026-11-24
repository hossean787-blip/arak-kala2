from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .models import Product, Order

@require_GET
@never_cache
def ready(request):
    try:
        # Ensure core tables exist, not merely that the SQLite file opens.
        Product.objects.values_list("pk",flat=True).first()
        Order.objects.values_list("pk",flat=True).first()
    except DatabaseError:
        return JsonResponse({"ok":False},status=503)
    return JsonResponse({"ok":True})
