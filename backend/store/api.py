"""JSON endpoints for the storefront and the native manager app."""
import base64
from collections import Counter
from datetime import timedelta
from functools import wraps
from hashlib import sha256
from io import BytesIO
import json
import re
from secrets import token_urlsafe
from uuid import UUID, uuid4

from django import forms
from django.conf import settings
from django.contrib.auth import login, logout
from django.core.exceptions import RequestDataTooBig, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from PIL import Image, ImageOps, UnidentifiedImageError

from .forms import CheckoutForm, CustomerLoginForm, CustomerRegistrationForm, ManagerAuthenticationForm, ProductForm
from .models import MAX_STOCK, Customer, ManagerToken, Order, Product, StockMovement
from .services import place_order, update_order
from .views import create_customer, is_manager

MAX_IMAGE_BYTES = 2 * 1024 * 1024
IMAGE_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


class ApiError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


def endpoint(*methods):
    def decorate(view):
        @never_cache
        @wraps(view)
        def handle(request, *args, **kwargs):
            if request.method not in methods:
                response = JsonResponse({"error": "روش درخواست مجاز نیست."}, status=405)
                response["Allow"] = ", ".join(methods)
                return response
            try:
                return view(request, *args, **kwargs)
            except ApiError as exc:
                return JsonResponse({"error": exc.message}, status=exc.status)
            except Http404:
                return JsonResponse({"error": "مورد درخواستی پیدا نشد."}, status=404)
            except RequestDataTooBig:
                return JsonResponse({"error": "حجم درخواست بیش از حد مجاز است."}, status=413)
        return handle
    return decorate


def payload(request):
    if request.content_type != "application/json":
        raise ApiError(415, "درخواست باید JSON باشد.")
    try:
        data = json.loads(request.body)
    except (ValueError, RecursionError):
        raise ApiError(400, "اطلاعات درخواست نامعتبر است.") from None
    if not isinstance(data, dict):
        raise ApiError(400, "اطلاعات درخواست نامعتبر است.")
    return data


def validate(form):
    if not form.is_valid():
        raise ApiError(400, next(iter(form.errors.values()))[0])
    return form.cleaned_data


def customer_for(request):
    if request.user.is_authenticated:
        customer = Customer.objects.filter(account=request.user).first()
        if customer:
            return customer
    raise ApiError(401, "ابتدا وارد حساب مشتری شوید.")


def customer_json(customer):
    return {"full_name": customer.name, "phone": customer.phone}


def manager_session(request):
    auth = request.headers.get("Authorization", "")
    if not re.fullmatch(r"Bearer [A-Za-z0-9_-]{43}", auth):
        raise ApiError(401, "ابتدا وارد حساب مدیریت شوید.")
    digest = sha256(auth[7:].encode()).hexdigest()
    token = (ManagerToken.objects.select_related("account")
             .filter(digest=digest, expires_at__gt=timezone.now()).first())
    if (token is None or not is_manager(token.account)
            or not constant_time_compare(token.auth_hash, token.account.get_session_auth_hash())):
        raise ApiError(401, "نشست مدیریت منقضی شده است.")
    return token


def product_json(product, *, manager=False):
    data = {
        "id": product.pk, "name": product.name, "description": product.description,
        "category": product.category, "price": product.actual_price, "stock": product.stock,
        "images": [default_storage.url(name) for name in product.images],
    }
    if manager:
        data.update(sku=product.sku, price=product.price, active=product.active,
                    discount_price=product.discount_price)
    return data


def order_json(order, *, manager=False):
    data = {
        "id": order.pk, "code": order.code, "total": order.total,
        "status": order.status, "status_label": order.get_status_display(),
        "created_at": int(order.created_at.timestamp()),
    }
    if manager:
        data.update(full_name=order.customer, phone=order.phone, address=order.address,
                    items=[{"name": line.name, "quantity": line.quantity, "unit_price": line.unit_price}
                           for line in order.lines.all()])
    return data


@ensure_csrf_cookie
@never_cache
def storefront(request):
    return render(request, "store/storefront.html")


@endpoint("GET")
def health(request):
    return JsonResponse({"ok": True})


@endpoint("GET")
def public_products(request, pk=None):
    products = Product.objects.filter(active=True)
    if pk is not None:
        return JsonResponse(product_json(get_object_or_404(products, pk=pk)))
    search = request.GET.get("search", "").strip()[:100]
    category = request.GET.get("category", "").strip()[:80]
    if search:
        products = products.filter(Q(name__icontains=search) | Q(description__icontains=search))
    if category:
        products = products.filter(category=category)
    return JsonResponse({"products": [product_json(product) for product in products]})


@endpoint("POST")
def customer_register(request):
    details = validate(CustomerRegistrationForm(payload(request)))
    try:
        account = create_customer(details)
    except IntegrityError:
        raise ApiError(409, "با این شماره یا نام کاربری امکان ثبت‌نام نیست.") from None
    login(request, account)
    return JsonResponse({"user": customer_json(account.customer)}, status=201)


@endpoint("POST")
def customer_login(request):
    data = payload(request)
    form = CustomerLoginForm(request, data={"username": data.get("username"), "password": data.get("password")})
    if not form.is_valid():
        raise ApiError(401, "موبایل، نام کاربری یا رمز عبور درست نیست.")
    user = form.get_user()
    login(request, user)
    return JsonResponse({"user": customer_json(user.customer)})


@endpoint("POST")
def customer_logout(request):
    customer_for(request)
    logout(request)
    return JsonResponse({"ok": True})


@endpoint("GET")
def current_customer(request):
    return JsonResponse(customer_json(customer_for(request)))


@endpoint("GET", "POST")
def customer_orders(request):
    customer = customer_for(request)
    if request.method == "GET":
        orders = Order.objects.filter(account=customer)[:200]
        return JsonResponse({"orders": [order_json(order) for order in orders]})

    data = payload(request)
    details = validate(CheckoutForm(data={
        "customer": data.get("full_name"), "phone": data.get("phone"), "address": data.get("address"),
    }))
    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not 1 <= len(raw_items) <= 50:
        raise ApiError(400, "سبد خرید باید بین ۱ تا ۵۰ ردیف داشته باشد.")
    items = Counter()
    for item in raw_items:
        if not isinstance(item, dict):
            raise ApiError(400, "اقلام سفارش معتبر نیستند.")
        product_id, quantity = item.get("product_id"), item.get("quantity")
        if (type(product_id) is not int or not 1 <= product_id < 2**63
                or type(quantity) is not int or not 1 <= quantity <= 1000):
            raise ApiError(400, "اقلام سفارش معتبر نیستند.")
        items[product_id] += quantity
    if any(quantity > 1000 for quantity in items.values()):
        raise ApiError(400, "تعداد درخواستی از حد مجاز بیشتر است.")
    try:
        token = UUID(str(data.get("token")))
    except ValueError:
        raise ApiError(400, "شناسه ثبت سفارش معتبر نیست.") from None
    try:
        order = place_order(token, details["customer"], details["phone"], details["address"], items, customer)
    except ValidationError as exc:
        raise ApiError(409, exc.messages[0]) from None
    if dict(order.lines.values_list("product_id", "quantity")) != dict(items):
        raise ApiError(409, "این شناسه قبلاً برای سبد دیگری استفاده شده است.")
    return JsonResponse({"order_id": order.pk, **order_json(order)}, status=201)


@csrf_exempt
@endpoint("POST")
def manager_login(request):
    data = payload(request)
    form = ManagerAuthenticationForm(request, data={"username": data.get("email"), "password": data.get("password")})
    if not form.is_valid() or not is_manager(form.get_user()):
        raise ApiError(401, "ایمیل یا رمز عبور درست نیست.")
    account = form.get_user()
    token = token_urlsafe(32)
    now = timezone.now()
    with transaction.atomic():
        ManagerToken.objects.filter(expires_at__lte=now).delete()
        ManagerToken.objects.create(account=account, digest=sha256(token.encode()).hexdigest(),
                                    expires_at=now + timedelta(hours=8), auth_hash=account.get_session_auth_hash())
    return JsonResponse({"token": token, "user": {"role": "admin"}})


@csrf_exempt
@endpoint("POST")
def manager_logout(request):
    manager_session(request).delete()
    return JsonResponse({"ok": True})


def image_names(urls):
    if not isinstance(urls, list) or len(urls) > 8:
        raise ApiError(400, "حداکثر ۸ تصویر مجاز است.")
    names = []
    for url in urls:
        if not isinstance(url, str) or not url.startswith(settings.MEDIA_URL):
            raise ApiError(400, "نشانی تصویر معتبر نیست.")
        name = url.removeprefix(settings.MEDIA_URL)
        if not re.fullmatch(r"products/[0-9a-f]{32}\.jpg", name) or not default_storage.exists(name):
            raise ApiError(400, "فایل تصویر پیدا نشد.")
        if name not in names:
            names.append(name)
    return names


@csrf_exempt
@endpoint("GET", "POST", "PATCH", "DELETE")
def manager_products(request, pk=None):
    manager_session(request)
    if request.method == "GET":
        if pk is not None:
            return JsonResponse(product_json(get_object_or_404(Product, pk=pk), manager=True))
        return JsonResponse({"products": [product_json(product, manager=True) for product in Product.objects.all()]})
    if (pk is None) != (request.method == "POST"):
        raise ApiError(405, "روش درخواست برای این مسیر مجاز نیست.")

    try:
        with transaction.atomic():
            product = get_object_or_404(Product.objects.select_for_update(), pk=pk) if pk is not None else Product()
            if request.method == "DELETE":
                product.active = False
                product.save(update_fields=["active"])
                return JsonResponse({"ok": True})
            data = payload(request)
            form_data = {field: data.get(field, getattr(product, field)) for field in ProductForm.Meta.fields}
            if "active" in data and type(data["active"]) is not bool:
                raise ApiError(400, "وضعیت کالا معتبر نیست.")
            if pk is None and not form_data["sku"]:
                form_data["sku"] = f"AK-{uuid4().hex.upper()}"
            previous_stock = product.stock
            if "expected_stock" in data and data["expected_stock"] != previous_stock:
                raise ApiError(409, "موجودی در این فاصله تغییر کرده است. فهرست کالاها را تازه کنید.")
            stock = validate(StockInput({"stock": data.get("stock", previous_stock)}))["stock"]
            form = ProductForm(form_data, instance=product)
            validate(form)
            product = form.save(commit=False)
            product.stock = stock
            if "images" in data:
                product.images = image_names(data["images"])
            product.save()
            if stock != previous_stock:
                StockMovement.objects.create(product=product, delta=stock - previous_stock, reason="مدیریت کالا در اپ")
    except IntegrityError:
        raise ApiError(409, "کد کالا یا بارکد تکراری است.") from None
    return JsonResponse({"id": product.pk, "ok": True}, status=201 if pk is None else 200)


class StockInput(forms.Form):
    stock = forms.IntegerField(min_value=0, max_value=MAX_STOCK)


@csrf_exempt
@endpoint("POST")
def manager_image(request):
    manager_session(request)
    data = payload(request)
    mime, encoded = data.get("mime"), data.get("base64")
    if not isinstance(mime, str) or mime not in IMAGE_FORMATS or not isinstance(encoded, str):
        raise ApiError(400, "فرمت تصویر معتبر نیست.")
    if len(encoded) > (MAX_IMAGE_BYTES + 2) // 3 * 4:
        raise ApiError(413, "حجم تصویر حداکثر ۲ مگابایت است.")
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_IMAGE_BYTES:
            raise ApiError(413, "حجم تصویر حداکثر ۲ مگابایت است.")
        with Image.open(BytesIO(raw)) as source:
            if source.format != IMAGE_FORMATS[mime] or source.width * source.height > 16_000_000:
                raise ApiError(400, "فرمت یا ابعاد تصویر معتبر نیست.")
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1600, 1600))
            output = BytesIO()
            image.save(output, "JPEG", quality=86)
    except (ValueError, UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ApiError(400, "محتوای تصویر معتبر نیست.") from None
    name = default_storage.save(f"products/{uuid4().hex}.jpg", ContentFile(output.getvalue()))
    return JsonResponse({"url": default_storage.url(name)}, status=201)


@endpoint("GET")
def manager_orders(request):
    manager_session(request)
    orders = Order.objects.prefetch_related("lines")[:200]
    return JsonResponse({"orders": [order_json(order, manager=True) for order in orders]})


@csrf_exempt
@endpoint("PATCH")
def manager_order_status(request, pk):
    manager_session(request)
    status = payload(request).get("status")
    if not isinstance(status, str) or status not in Order.Status.values:
        raise ApiError(400, "وضعیت سفارش معتبر نیست.")
    try:
        update_order(pk, status)
    except Order.DoesNotExist:
        raise Http404 from None
    except ValidationError as exc:
        raise ApiError(409, exc.messages[0]) from None
    return JsonResponse({"ok": True})


@endpoint("GET")
def manager_stats(request):
    manager_session(request)
    products = Product.objects.filter(active=True)
    sales = Order.objects.filter(status__in=[Order.Status.CONFIRMED, Order.Status.SHIPPED, Order.Status.DELIVERED])
    return JsonResponse({"products": products.count(), "orders": Order.objects.count(),
                         "low_stock": products.filter(stock__lt=5).count(),
                         "sales_total": sales.aggregate(total=Sum("total"))["total"] or 0})
