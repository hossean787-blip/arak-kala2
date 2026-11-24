"""Server-calculated, immutable checkout pricing; no online payment is implied."""
from django.core.exceptions import ValidationError
from .models import Coupon, ShippingMethod, Order, Product

def quote(cart,coupon_code="",shipping_id=None,*,locked=False,lines=None):
    if not cart:
        raise ValidationError("سبد خرید خالی است.")
    if lines is None:
        products=Product.objects.filter(active=True,pk__in=cart).in_bulk()
        if len(products)!=len(cart) or any(products[pk].stock<qty for pk,qty in cart.items()):
            raise ValidationError("موجودی یا وضعیت کالا تغییر کرده است.")
        items=[[pk,qty,products[pk].actual_price] for pk,qty in sorted(cart.items())]
    else:
        items=[[line.product_id,line.quantity,line.unit_price] for line in lines]
    subtotal=sum(qty*price for _,qty,price in items)
    methods=ShippingMethod.objects.filter(active=True)
    if locked: methods=methods.select_for_update()
    method=None
    if shipping_id is not None:
        method=methods.filter(pk=shipping_id).first()
        if method is None: raise ValidationError("روش ارسال معتبر نیست.")
    elif methods.exists():
        raise ValidationError("روش ارسال را انتخاب کنید.")
    fee=method.fee if method else 0
    coupons=Coupon.objects.filter(active=True)
    if locked: coupons=coupons.select_for_update()
    coupon=None
    discount=0
    if coupon_code:
        coupon=coupons.filter(code=coupon_code).first()
        if coupon is None or subtotal<coupon.minimum or Order.objects.filter(coupon=coupon).exclude(status=Order.Status.CANCELLED).count()>=coupon.max_uses:
            raise ValidationError("کد تخفیف معتبر نیست یا شرایط استفاده را ندارد.")
        discount=min(subtotal,coupon.amount)
    return {"items":items,"subtotal":subtotal,"discount":discount,"shipping_fee":fee,
            "coupon_code":coupon.code if coupon else "","coupon_id":coupon.pk if coupon else None,
            "shipping_id":method.pk if method else None,"shipping_name":method.name if method else "",
            "total":subtotal-discount+fee}
