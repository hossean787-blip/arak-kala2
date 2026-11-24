"""Shared database-backed throttling for sensitive authentication and tracking routes."""
from ipaddress import ip_address
from time import time

from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models import F
from django.http import JsonResponse, HttpResponse
from django.utils.crypto import salted_hmac

from .models import AuthThrottle


# Separate buckets keep an exhausted tracking/customer bucket from blocking a manager.
RULES = {
    "/api/admin/session": ("manager", 10),
    "/manager/login/": ("manager", 10),
    "/api/auth/login": ("customer_login", 30),
    "/shop/account/login/": ("customer_login", 30),
    "/api/auth/register": ("register", 15),
    "/shop/account/register/": ("register", 15),
    "/shop/track/": ("track", 30),
    "/login/": ("customer_login", 30),
    "/register/": ("register", 15),
    "/tracking/": ("track", 30),
}
WINDOW = 300


def client_ip(request):
    value = request.META.get("REMOTE_ADDR", "")
    if settings.ARAK_TRUST_REAL_IP:
        value = request.META.get("HTTP_X_REAL_IP", value)
    try:
        return str(ip_address(value))
    except ValueError:
        return "unknown"


class AuthThrottleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rule = RULES.get(request.path_info)
        if request.method != "POST" or rule is None:
            return self.get_response(request)
        bucket, limit = rule
        now = int(time())
        window = now // WINDOW
        # Store an HMAC rather than the raw IP address.
        key = salted_hmac("arak-auth-throttle", f"{bucket}:{client_ip(request)}", algorithm="sha256").hexdigest()
        try:
            with transaction.atomic():
                row, created = AuthThrottle.objects.select_for_update().get_or_create(
                    key=key, defaults={"window": window, "count": 0}
                )
                if row.window != window:
                    row.window = window
                    row.count = 0
                    row.save(update_fields=["window", "count"])
                allowed = AuthThrottle.objects.filter(key=key, window=window, count__lt=limit).update(
                    count=F("count") + 1
                )
                # Bound stale rows without a separate service; cleanup is transactional.
                if created:
                    AuthThrottle.objects.filter(window__lt=window - 288).delete()
        except DatabaseError:
            return self.reject(request, 503, 30)
        if not allowed:
            return self.reject(request, 429, WINDOW - now % WINDOW)
        return self.get_response(request)

    @staticmethod
    def reject(request, status, retry):
        message = "درخواست‌های زیادی ارسال شده است. کمی بعد دوباره تلاش کنید." if status == 429 else "سرویس موقتاً در دسترس نیست."
        response = (JsonResponse({"error": message}, status=status) if request.path_info.startswith("/api/")
                    else HttpResponse(message, status=status, content_type="text/plain; charset=utf-8"))
        response["Retry-After"] = str(retry)
        response["Cache-Control"] = "no-store"
        return response
