from collections import Counter
from hashlib import sha256
import json
from secrets import token_hex

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from .models import MAX_STOCK, Order, OrderLine, Product, Sale, SaleLine, StockMovement


@transaction.atomic
def increase_stock(product, quantity, reason):
    if type(quantity) is not int or not 1 <= quantity <= MAX_STOCK:
        raise ValidationError("تعداد ورود موجودی معتبر نیست.")
    updated = Product.objects.filter(pk=product.pk, stock__lte=MAX_STOCK - quantity).update(
        stock=F("stock") + quantity
    )
    if updated != 1:
        raise ValidationError("موجودی از سقف مجاز عبور می‌کند.")
    StockMovement.objects.create(product=product, delta=quantity, reason=reason)


@transaction.atomic
def adjust_stock(product_id, expected, desired, reason):
    if type(expected) is not int or type(desired) is not int or not 0<=expected<=MAX_STOCK or not 0<=desired<=MAX_STOCK:
        raise ValidationError("موجودی معتبر نیست.")
    product=Product.objects.select_for_update().get(pk=product_id)
    if product.stock!=expected:
        raise ValidationError("موجودی تغییر کرده است؛ صفحه را تازه کنید.")
    if desired!=expected:
        product.stock=desired
        product.save(update_fields=["stock"])
        StockMovement.objects.create(product=product,delta=desired-expected,reason=reason)
    return product


@transaction.atomic
def record_sale(token, customer, selected):
    quantities = Counter()
    for product_id, quantity in selected:
        quantities[product_id] += quantity
    if not quantities or any(quantity <= 0 for quantity in quantities.values()):
        raise ValidationError("دست‌کم یک کالا با تعداد معتبر انتخاب کنید.")
    items = sorted(quantities.items())
    fingerprint = sha256(json.dumps([customer, items], ensure_ascii=False).encode()).hexdigest()

    sale, created = Sale.objects.get_or_create(token=token, defaults={
        "customer": customer, "fingerprint": fingerprint,
    })
    if not created:
        if sale.fingerprint != fingerprint:
            raise ValidationError("این فرم قبلاً ثبت شده است. فروش تازه‌ای شروع کنید.")
        return sale

    lines = []
    moves = []
    for product_id, quantity in items:
        product = reserve_product(product_id, quantity)
        lines.append(SaleLine(sale=sale, product=product, sku=product.sku,
                              name=product.name, quantity=quantity, unit_price=product.actual_price))
        moves.append(StockMovement(product=product, sale=sale, delta=-quantity, reason="فروش"))
    SaleLine.objects.bulk_create(lines)
    StockMovement.objects.bulk_create(moves)
    sale.total = sum(line.total for line in lines)
    sale.save(update_fields=["total"])
    return sale


def reserve_product(product_id, quantity):
    if type(quantity) is not int or not 1 <= quantity <= MAX_STOCK:
        raise ValidationError("تعداد کالا معتبر نیست.")
    try:
        product = Product.objects.select_for_update().get(pk=product_id, active=True)
    except Product.DoesNotExist as exc:
        raise ValidationError("یکی از کالاها از فروش خارج شده است.") from exc
    updated = Product.objects.filter(pk=product_id, stock__gte=quantity).update(
        stock=F("stock") - quantity
    )
    if updated != 1:
        raise ValidationError(f"موجودی «{product.name}» کافی نیست.")
    return product


@transaction.atomic
def place_order(token, customer, phone, address, cart, account=None):
    if not cart or any(type(pid) is not int or pid < 1 or type(qty) is not int
                       or not 1 <= qty <= MAX_STOCK for pid, qty in cart.items()):
        raise ValidationError("سبد خرید معتبر نیست.")
    order, created = Order.objects.get_or_create(token=token, defaults={
        "customer": customer, "phone": phone, "address": address,
        "account": account, "code": token_hex(10).upper(),
    })
    if not created:
        if (order.customer, order.phone, order.address, order.account) != (customer, phone, address, account):
            raise ValidationError("این فرم قبلاً ثبت شده است. لطفاً سفارش جدیدی شروع کنید.")
        if dict(order.lines.values_list("product_id", "quantity")) != dict(cart):
            raise ValidationError("این شناسه قبلاً برای سبد دیگری استفاده شده است.")
        return order

    lines = []
    movements = []
    for product_id, quantity in sorted(cart.items()):
        product = reserve_product(product_id, quantity)
        lines.append(OrderLine(order=order, product=product, name=product.name,
                               quantity=quantity, unit_price=product.actual_price))
        movements.append(StockMovement(product=product, order=order,
                                       delta=-quantity, reason="سفارش اینترنتی"))
    OrderLine.objects.bulk_create(lines)
    StockMovement.objects.bulk_create(movements)
    order.total = sum(line.total for line in lines)
    order.save(update_fields=["total"])
    return order


NEXT_STATUS = {
    Order.Status.NEW: (Order.Status.CONFIRMED, Order.Status.CANCELLED),
    Order.Status.CONFIRMED: (Order.Status.SHIPPED, Order.Status.CANCELLED),
    Order.Status.SHIPPED: (Order.Status.DELIVERED,),
}


@transaction.atomic
def update_order(order_id, status):
    order = Order.objects.select_for_update().get(pk=order_id)
    if status == order.status:
        return
    if status not in NEXT_STATUS.get(order.status, ()):
        raise ValidationError("تغییر به این وضعیت مجاز نیست.")
    if status == Order.Status.CANCELLED:
        for line in order.lines.select_related("product").order_by("product_id"):
            updated = Product.objects.filter(pk=line.product_id, stock__lte=MAX_STOCK - line.quantity).update(
                stock=F("stock") + line.quantity
            )
            if updated != 1:
                raise ValidationError(f"بازگشت «{line.name}» از سقف موجودی عبور می‌کند.")
            StockMovement.objects.create(product_id=line.product_id, order=order,
                                         delta=line.quantity, reason="لغو سفارش")
    order.status = status
    order.save(update_fields=["status"])
