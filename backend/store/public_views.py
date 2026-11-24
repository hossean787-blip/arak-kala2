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
from .favorites import favorite_ids, set_favorite

@never_cache
@ensure_csrf_cookie
def home(request):
    products = Product.objects.filter(active=True)
    return render(request, "store/public_home.html", {"products": products.order_by("-pk")[:8], "discounts": products.filter(stock__gt=0,discount_price__isnull=False).order_by("-pk")[:4], "favorite_ids":favorite_ids(request)})

def categories(request):
    from django.db.models import Count
    groups = Product.objects.filter(active=True).exclude(category="").values("category").annotate(count=Count("pk")).order_by("category")
    return render(request, "store/categories.html", {"groups": groups})

@never_cache
def favorites(request):
    ids=favorite_ids(request)
    return render(request,"store/favorites.html",{"products":Product.objects.filter(active=True,pk__in=ids),"favorite_ids":ids})

@require_POST
@never_cache
def toggle_favorite(request,pk):
    product=get_object_or_404(Product,pk=pk,active=True)
    action=request.POST.get("action","")
    desired={"add":True,"remove":False}.get(action)
    if not set_favorite(request,product,desired):
        messages.error(request,"حداکثر ۱۰۰ محصول در علاقه‌مندی‌ها.")
    source=request.POST.get("source")
    if source=="favorites":
        return redirect("favorites")
    if source=="catalog":
        return redirect("public_catalog")
    return redirect("public_product",pk=pk)

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

def robots(request):
    from django.http import HttpResponse
    content="User-agent: *\nDisallow: /manager/\nDisallow: /api/\nDisallow: /pos/\nDisallow: /account/\nDisallow: /cart/\nDisallow: /checkout/\nDisallow: /favorites/\nDisallow: /login/\nDisallow: /register/\nDisallow: /shop/\nDisallow: /search/\nSitemap: "+request.build_absolute_uri(reverse("sitemap"))+"\n"
    return HttpResponse(content,content_type="text/plain; charset=utf-8")

def sitemap(request):
    from django.http import HttpResponse
    from xml.etree.ElementTree import Element, SubElement, tostring
    root=Element("urlset",xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    paths=[reverse(name) for name in ("home","public_catalog","categories","about","contact","terms","privacy")]
    paths.extend(reverse("public_product",args=[pk]) for pk in Product.objects.filter(active=True).order_by("pk").values_list("pk",flat=True)[:49000])
    for path in paths:
        SubElement(SubElement(root,"url"),"loc").text=request.build_absolute_uri(path)
    return HttpResponse(tostring(root,encoding="utf-8",xml_declaration=True),content_type="application/xml; charset=utf-8")
