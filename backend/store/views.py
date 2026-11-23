from functools import wraps
from uuid import UUID, uuid4

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import LoginView, redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .forms import (CartLineForm, CheckoutForm, CustomerLoginForm, CustomerRegistrationForm,
                    LineForm, ManagerAuthenticationForm, ProductForm, SaleForm, SaleLineFormSet,
                    StockForm, TrackingForm)
from .models import Customer, Order, Product, Sale
from .services import NEXT_STATUS, increase_stock, place_order, record_sale, update_order


class ManagerLogin(LoginView):
    template_name = "store/login.html"
    authentication_form = ManagerAuthenticationForm


class CustomerLogin(LoginView):
    template_name = "store/customer_login.html"
    authentication_form = CustomerLoginForm

    def get_default_redirect_url(self):
        return reverse("customer_orders")


@transaction.atomic
def create_customer(details):
    account = get_user_model().objects.create_user(
        username=f"customer_{details['phone']}", password=details["password"]
    )
    Customer.objects.create(account=account, name=details["name"],
                            phone=details["phone"], alias=details["alias"])
    return account


def is_manager(user):
    return (user.is_authenticated and user.is_active
            and user.get_username().lower() == settings.STORE_MANAGER_EMAIL
            and user.email.lower() == settings.STORE_MANAGER_EMAIL)


@never_cache
def customer_register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = CustomerRegistrationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        details = form.cleaned_data
        try:
            account = create_customer(details)
        except IntegrityError:
            form.add_error(None, "با این شماره یا نام کاربری امکان ثبت‌نام نیست.")
        else:
            login(request, account)
            return redirect("customer_orders")
    return render(request, "store/form.html", {
        "form": form, "title": "ثبت‌نام مشتری", "submit": "ایجاد حساب",
    })


@never_cache
def customer_orders(request):
    if not request.user.is_authenticated:
        return redirect("customer_login")
    customer = get_object_or_404(Customer, account=request.user)
    page = Paginator(Order.objects.filter(account=customer), 30).get_page(request.GET.get("page"))
    return render(request, "store/customer_orders.html", {"page": page})


def manager_only(view):
    @never_cache
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_manager(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return guarded


def home(request):
    return render(request, "store/home.html")


def catalog(request):
    products = Product.objects.filter(active=True)
    search = request.GET.get("q", "").strip()[:100]
    category = request.GET.get("category", "").strip()[:80]
    sort = request.GET.get("sort", "")
    categories = products.exclude(category="").order_by("category").values_list(
        "category", flat=True
    ).distinct()
    if search:
        products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search)
                                   | Q(barcode__iexact=search))
    if category:
        products = products.filter(category=category)
    if sort in {"price", "-price"}:
        products = products.annotate(effective=Coalesce("discount_price", "price"))
        products = products.order_by("-effective" if sort == "-price" else "effective", "pk")
    page = Paginator(products, 24).get_page(request.GET.get("page"))
    return render(request, "store/catalog.html", {
        "page": page, "categories": categories, "selected": category, "q": search, "sort": sort,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, active=True)
    return render(request, "store/product_detail.html", {"product": product})


@require_POST
def change_cart(request):
    form = CartLineForm(request.POST)
    if not form.is_valid():
        messages.error(request, "تعداد کالا معتبر نیست.")
        return redirect("cart")
    product_id = form.cleaned_data["product"]
    quantity = form.cleaned_data["quantity"]
    basket = request.session.get("cart", {})
    if quantity:
        if len(basket) >= 30 and str(product_id) not in basket:
            messages.error(request, "سبد خرید حداکثر ۳۰ ردیف کالا دارد.")
            return redirect("cart")
        product = get_object_or_404(Product, pk=product_id, active=True)
        if quantity > product.stock:
            messages.error(request, "موجودی کافی نیست.")
            return redirect("cart")
        basket[str(product_id)] = quantity
    else:
        basket.pop(str(product_id), None)
    request.session["cart"] = basket
    request.session["order_token"] = str(uuid4())
    return redirect("cart")


@never_cache
def cart(request):
    basket = request.session.get("cart", {})
    products = Product.objects.in_bulk(int(product_id) for product_id in basket)
    rows = []
    for product_id, quantity in basket.items():
        product = products.get(int(product_id))
        if product is not None:
            rows.append((product, quantity, product.actual_price * quantity))
    can_order = bool(rows) and all(product.active and quantity <= product.stock
                                  for product, quantity, _ in rows)
    return render(request, "store/cart.html", {
        "rows": rows, "total": sum(total for _, _, total in rows), "can_order": can_order,
    })


@never_cache
def checkout(request):
    basket = request.session.get("cart", {})
    if not basket:
        return redirect("order_done" if request.session.get("last_order") else "cart")
    account = (Customer.objects.filter(account=request.user).first()
               if request.user.is_authenticated else None)
    initial = {"customer": account.name, "phone": account.phone} if account else {}
    form = CheckoutForm(request.POST if request.method == "POST" else None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            order = place_order(UUID(request.session["order_token"]),
                                form.cleaned_data["customer"], form.cleaned_data["phone"],
                                form.cleaned_data["address"],
                                {int(key): quantity for key, quantity in basket.items()}, account)
        except ValidationError as error:
            form.add_error(None, error)
        except (IntegrityError, OperationalError):
            form.add_error(None, "ثبت سفارش کامل نشد. دوباره تلاش کنید.")
        else:
            request.session.pop("cart", None)
            request.session.pop("order_token", None)
            request.session["last_order"] = order.code
            return redirect("order_done")
    return render(request, "store/form.html", {"title": "ثبت سفارش", "form": form, "submit": "ثبت سفارش"})


@never_cache
def order_done(request):
    code = request.session.get("last_order")
    if not code:
        return redirect("track")
    return render(request, "store/order_done.html", {"code": code})


@never_cache
def track(request):
    form = TrackingForm(request.POST if request.method == "POST" else None)
    order = None
    if request.method == "POST" and form.is_valid():
        order = Order.objects.filter(code=form.cleaned_data["code"].upper(),
                                     phone=form.cleaned_data["phone"]).first()
        if order is None:
            form.add_error(None, "سفارشی با این کد و شماره موبایل پیدا نشد.")
    return render(request, "store/track.html", {"form": form, "order": order})


@manager_only
def dashboard(request):
    sales = Sale.objects.filter(created_at__date=timezone.localdate())
    return render(request, "store/dashboard.html", {
        "active_count": Product.objects.filter(active=True).count(),
        "open_orders": Order.objects.filter(status__in=[Order.Status.NEW, Order.Status.CONFIRMED]).count(),
        "today_sales": sales.count(), "today_total": sales.aggregate(total=Sum("total"))["total"] or 0,
    })


@manager_only
def products(request):
    query = request.GET.get("q", "").strip()[:100]
    products = Product.objects.all()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(sku__icontains=query)
                                   | Q(barcode__iexact=query))
    page = Paginator(products, 30).get_page(request.GET.get("page"))
    return render(request, "store/products.html", {"page": page, "q": query})


@manager_only
def product_edit(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk is not None else None
    form = ProductForm(request.POST if request.method == "POST" else None, instance=product)
    if request.method == "POST" and form.is_valid():
        try:
            if pk is None:
                form.save()
            else:
                form.save(commit=False).save(update_fields=ProductForm.Meta.fields)
        except IntegrityError:
            form.add_error(None, "این کد کالا یا بارکد قبلاً ثبت شده است.")
        else:
            messages.success(request, "کالا ذخیره شد.")
            return redirect("products")
    return render(request, "store/form.html", {
        "form": form, "title": "ویرایش کالا" if product else "کالای جدید",
    })


@manager_only
def add_stock(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = StockForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            increase_stock(product, form.cleaned_data["quantity"], form.cleaned_data["reason"])
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "ورود موجودی ثبت شد.")
            return redirect("products")
    return render(request, "store/form.html", {"form": form, "title": f"ورود موجودی {product.name}"})


@manager_only
def pos(request):
    post = request.POST if request.method == "POST" else None
    form = SaleForm(post, initial={"token": uuid4()})
    lines = forms.formset_factory(LineForm, formset=SaleLineFormSet, extra=3,
                                  max_num=30, validate_max=True, absolute_max=30)(post, prefix="items")
    if post is not None and form.is_valid() and lines.is_valid():
        selected = [(row.cleaned_data["product"].pk, row.cleaned_data["quantity"])
                    for row in lines if row.cleaned_data]
        try:
            sale = record_sale(form.cleaned_data["token"], form.cleaned_data["customer"], selected)
        except ValidationError as error:
            form.add_error(None, error)
        except OperationalError:
            form.add_error(None, "ثبت فروش کامل نشد. دوباره تلاش کنید.")
        else:
            return redirect("receipt", pk=sale.pk)
    return render(request, "store/pos.html", {"form": form, "lines": lines})


@manager_only
def sale_list(request):
    queryset = Sale.objects.all()
    date_filter = None
    raw_date = request.GET.get("date", "")
    try:
        date_filter = forms.DateField(required=False).clean(raw_date)
    except ValidationError:
        messages.error(request, "تاریخ واردشده معتبر نیست.")
    if date_filter:
        queryset = queryset.filter(created_at__date=date_filter)
    page = Paginator(queryset, 30).get_page(request.GET.get("page"))
    return render(request, "store/sales.html", {
        "page": page, "total": queryset.aggregate(total=Sum("total"))["total"] or 0, "date": raw_date,
    })


@manager_only
def receipt(request, pk):
    sale = get_object_or_404(Sale.objects.prefetch_related("lines"), pk=pk)
    return render(request, "store/receipt.html", {"sale": sale})


@manager_only
def orders(request):
    return render(request, "store/orders.html", {
        "page": Paginator(Order.objects.all(), 30).get_page(request.GET.get("page")),
    })


@manager_only
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related("lines"), pk=pk)
    if request.method == "POST":
        try:
            update_order(pk, request.POST.get("status", ""))
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            return redirect("order_detail", pk=pk)
    choices = [(state, state.label) for state in NEXT_STATUS.get(order.status, ())]
    return render(request, "store/order_detail.html", {"order": order, "choices": choices})
