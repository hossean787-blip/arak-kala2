from uuid import uuid4
from django.test import TestCase, Client
from django.core.exceptions import ValidationError
from django.core import signing
from django.contrib.auth import get_user_model
from django.conf import settings
from .models import Product,Coupon,ShippingMethod,Order,StockMovement
from .services import place_order,update_order
from .pricing import quote

class CheckoutPricingTests(TestCase):
    def setUp(self):
        self.product=Product.objects.create(sku="PRICE-FIXTURE",name="کالای قیمت",stock=6,price=2000,discount_price=1500)
        self.coupon=Coupon.objects.create(code="SAVE",amount=500,minimum=1000,max_uses=1)
        self.ship=ShippingMethod.objects.create(name="ارسال آزمون",fee=300,active=True)
        self.items={self.product.pk:2}
    def test_price_snapshot_coupon_limit_and_rollback(self):
        price=quote(self.items,"SAVE",self.ship.pk)
        self.assertEqual(price["total"],2800)
        token=uuid4()
        order=place_order(token,"مشتری","09120000001","نشانی",self.items,coupon_code="SAVE",shipping_id=self.ship.pk,expected_quote=price)
        self.assertEqual((order.subtotal,order.discount,order.shipping_fee,order.total),(3000,500,300,2800))
        self.assertEqual(place_order(token,"مشتری","09120000001","نشانی",self.items,coupon_code="SAVE",shipping_id=self.ship.pk).pk,order.pk)
        with self.assertRaises(ValidationError):
            place_order(uuid4(),"مشتری","09120000001","نشانی",self.items,coupon_code="SAVE",shipping_id=self.ship.pk)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock,4)
        self.assertEqual(Order.objects.count(),1)
        update_order(order.pk,Order.Status.CANCELLED)
        self.assertEqual(quote(self.items,"SAVE",self.ship.pk)["discount"],500)
    def test_web_signed_quote_and_stale_price(self):
        self.client.post("/cart/update/",{"product":self.product.pk,"quantity":2})
        data={"customer":"مشتری","phone":"09120000001","address":"نشانی","shipping_id":self.ship.pk,"coupon_code":"SAVE"}
        response=self.client.post("/checkout/",{**data,"intent":"quote"})
        self.assertEqual(response.context["priced"]["total"],2800)
        sig=response.context["price_quote"]
        self.assertFalse(Order.objects.exists())
        Product.objects.filter(pk=self.product.pk).update(discount_price=1600)
        response=self.client.post("/checkout/",{**data,"price_quote":sig})
        self.assertEqual(response.status_code,200)
        self.assertFalse(Order.objects.exists())
        self.assertRedirects(self.client.post("/checkout/",{**data,"price_quote":response.context["price_quote"]}),"/checkout/complete/")
        self.assertEqual(Order.objects.get().total,3000)
    def test_unconfigured_or_invalid_shipping_and_permissions(self):
        with self.assertRaises(ValidationError): quote(self.items)
        with self.assertRaises(ValidationError): quote(self.items,"UNKNOWN",self.ship.pk)
        stranger=Client()
        stranger.force_login(get_user_model().objects.create_user(username="pricing-fixture",password=uuid4().hex))
        self.assertEqual(stranger.get("/manager/coupons/").status_code,403)
        self.assertEqual(stranger.post("/manager/shipping/",{"name":"invalid","fee":0}).status_code,403)
