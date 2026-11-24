"""Server-rendered public pages; shares Django sessions, products and order services."""
import json
from uuid import uuid4
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from .forms import SavedAddressForm
from .models import Customer, Product, SavedAddress

@ensure_csrf_cookie
def home(request):
    products = Product.objects.filter(active=True)
    return render(request, "store/public_home.html", {"products": products[:8]})

def categories(request):
    from django.db.models import Count
    groups = Product.objects.filter(active=True).exclude(category="").values("category").annotate(count=Count("pk")).order_by("category")
    return render(request, "store/categories.html", {"groups": groups})

@never_cache
def favorites(request):
    return render(request, "store/favorites.html", {"products": Product.objects.filter(active=True, pk__in=request.session.get("favorites", []))})

@require_POST
def toggle_favorite(request, pk):
    get_object_or_404(Product, pk=pk, active=True)
    values = list(request.session.get("favorites", []))
    if pk in values:
        values.remove(pk)
    elif len(values) < 100:
        values.append(pk)
    else:
        messages.error(request, "حداکثر ۱۰۰ محصول در علاقه‌مندی‌ها.")
    request.session["favorites"] = values
    return redirect("favorites" if request.POST.get("source") == "favorites" else "public_product", **({} if request.POST.get("source") == "favorites" else {"pk":pk}))

def get_customer(request):
    if not request.user.is_authenticated:
        return None
    customer = Customer.objects.filter(account=request.user).first()
    if customer is None:
        raise PermissionDenied
    return customer

@never_cache
def account(request):
    customer = get_customer(request)
    if customer is None:
        return redirect_to_login(request.path, reverse("public_login"))
    return render(request, "store/account.html", {"customer":customer})

@never_cache
def addresses(request, pk=None):
    customer = get_customer(request)
    if customer is None:
        return redirect_to_login(request.path, reverse("public_login"))
    address = get_object_or_404(SavedAddress, customer=customer, pk=pk) if pk is not None else None
    form = SavedAddressForm(request.POST if request.method == "POST" else None, instance=address)
    if request.method == "POST" and form.is_valid():
        if address is None and customer.addresses.count() >= 20:
            form.add_error(None, "حداکثر ۲۰ نشانی ثبت کنید.")
        else:
            item = form.save(commit=False)
            item.customer = customer
            item.save()
            messages.success(request, "نشانی ذخیره شد.")
            return redirect("addresses")
    return render(request, "store/addresses.html", {"form":form, "addresses":customer.addresses.all(), "editing":address})

@require_POST
@never_cache
def remove_address(request, pk):
    customer = get_customer(request)
    if customer is None:
        return redirect_to_login(request.path, reverse("public_login"))
    get_object_or_404(SavedAddress, customer=customer, pk=pk).delete()
    return redirect("addresses")

@require_POST
@never_cache
def import_cart(request):
    # Merge the previous storefront's local browser basket without duplicating quantities.
    try:
        payload = json.loads(request.body)
    except (ValueError, RecursionError):
        return JsonResponse({"ok":False}, status=400)
    if not isinstance(payload, list) or len(payload) > 50:
        return JsonResponse({"ok":False}, status=400)
    if any(not isinstance(i,dict) or type(i.get("id")) is not int or not 0 < i["id"] < 2**63 or type(i.get("quantity")) is not int or not 1 <= i["quantity"] <= 1000 for i in payload):
        return JsonResponse({"ok":False}, status=400)
    basket = dict(request.session.get("cart", {}))
    if request.session.get("legacy_cart_imported"):
        return JsonResponse({"ok":True})
    products = Product.objects.filter(active=True, pk__in=[i["id"] for i in payload]).in_bulk()
    for item in payload:
        key = str(item["id"])
        product = products.get(item["id"])
        if product and product.stock and (key in basket or len(basket) < 30):
            basket[key] = max(basket.get(key,0),min(item["quantity"],product.stock))
    request.session["cart"] = basket
    request.session["order_token"] = str(uuid4())
    request.session["legacy_cart_imported"] = True
    return JsonResponse({"ok":True})

def information(request, section):
    titles = {"about":"درباره اراک کالا","contact":"تماس با ما","terms":"شرایط خرید","privacy":"حریم خصوصی"}
    if section not in titles:
        raise Http404
    return render(request, "store/information.html", {"section":section,"title":titles[section]})
