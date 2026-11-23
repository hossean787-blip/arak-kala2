from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Customer, Order, Product, Sale, StockMovement


class StoreWorkflowTests(TestCase):
    password = "fresh-unique-test-passphrase-43"

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            settings.STORE_MANAGER_EMAIL, email=settings.STORE_MANAGER_EMAIL, password=cls.password,
        )
        cls.item = Product.objects.create(sku="TEST-01", name="کالای آزمایشی", category="نمونه",
                                          price=50000, discount_price=42000, stock=5)
        cls.second = Product.objects.create(sku="TEST-02", name="نمونه دوم", price=31000, stock=1)

    def test_single_manager_login(self):
        self.assertRedirects(self.client.get(reverse("dashboard")),
                             reverse("login") + "?next=/manager/", fetch_redirect_response=False)
        secondary = get_user_model().objects.create_user(
            "other@example.com", email="other@example.com", password=self.password, is_staff=True,
        )
        response = self.client.post(reverse("login"), {
            "username": secondary.username, "password": self.password,
        })
        self.assertContains(response, "ایمیل یا رمز")
        self.client.force_login(secondary)
        self.assertEqual(self.client.get(reverse("orders")).status_code, 403)
        self.client.logout()
        self.assertRedirects(self.client.post(reverse("login"), {
            "username": settings.STORE_MANAGER_EMAIL.upper(), "password": self.password,
        }), reverse("dashboard"))
        self.assertEqual(self.client.get("/auth/register.php").status_code, 404)
        self.assertEqual(self.client.get("/manager/register/").status_code, 404)

    def test_storefront_cart_order_tracking_and_cancel(self):
        response = self.client.get(reverse("catalog"), {"category": "نمونه", "sort": "price"})
        self.assertContains(response, self.item.name)
        self.assertNotContains(response, self.second.name)
        self.assertContains(self.client.get(reverse("product_detail", args=[self.item.pk])), "افزودن به سبد")
        self.client.post(reverse("change_cart"), {"product": self.item.pk, "quantity": 2})
        self.assertContains(self.client.get(reverse("cart")), self.item.name)
        checkout = {"customer": "خریدار آزمایشی", "phone": "۰۹۱۲۰۰۰۰۰۰۰", "address": "نشانی آزمایشی"}
        self.assertRedirects(self.client.post(reverse("checkout"), checkout), reverse("order_done"))
        order = Order.objects.get()
        self.assertEqual(order.phone, "09120000000")
        self.assertEqual(order.total, 84000)
        self.client.post(reverse("checkout"), checkout)
        self.assertEqual(Order.objects.count(), 1)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 3)
        bad = self.client.post(reverse("track"), {"code": order.code, "phone": "09121111111"})
        self.assertNotContains(bad, "در انتظار بررسی")
        good = self.client.post(reverse("track"), {"code": order.code, "phone": order.phone})
        self.assertContains(good, "در انتظار بررسی")
        self.client.force_login(self.owner)
        self.client.post(reverse("order_detail", args=[order.pk]), {"status": "cancelled"})
        self.client.post(reverse("order_detail", args=[order.pk]), {"status": "cancelled"})
        self.item.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.item.stock, 5)
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(StockMovement.objects.filter(order=order).count(), 2)

    def test_customer_account_cannot_enter_manager_or_see_another_orders(self):
        register = reverse("customer_register")
        self.assertRedirects(self.client.post(register, {
            "name": "خریدار اول", "phone": "09123333333", "alias": "BuyerOne", "password": self.password,
        }), reverse("customer_orders"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)
        self.client.post(reverse("change_cart"), {"product": self.item.pk, "quantity": 1})
        self.client.post(reverse("checkout"), {
            "customer": "خریدار اول", "phone": "09123333333", "address": "نشانی آزمایشی",
        })
        order = Order.objects.get()
        self.assertEqual(order.account, Customer.objects.get())
        self.assertContains(self.client.get(reverse("customer_orders")), order.code)
        self.client.logout()
        self.assertRedirects(self.client.post(reverse("customer_login"), {
            "username": "buyerone", "password": self.password,
        }), reverse("customer_orders"))
        stranger = Client()
        stranger.post(register, {
            "name": "خریدار دوم", "phone": "09124444444", "alias": "", "password": self.password,
        })
        self.assertNotContains(stranger.get(reverse("customer_orders")), order.code)

    def test_pos_snapshots_prices_retries_and_rolls_back_short_stock(self):
        self.client.force_login(self.owner)
        pos = reverse("pos")
        self.assertContains(self.client.get(pos), "ثبت فروش حضوری")
        data = {"token": str(uuid4()), "customer": "نمونه", "items-TOTAL_FORMS": 2,
                "items-INITIAL_FORMS": 0, "items-0-product": self.item.pk,
                "items-0-quantity": 2, "items-1-product": self.second.pk, "items-1-quantity": 2}
        self.assertContains(self.client.post(pos, data), "کافی نیست")
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 5)
        self.assertFalse(Sale.objects.exists())
        data["items-1-quantity"] = 1
        response = self.client.post(pos, data)
        sale = Sale.objects.get()
        self.assertRedirects(response, reverse("receipt", args=[sale.pk]))
        self.assertRedirects(self.client.post(pos, data), response.url)
        self.assertEqual(Sale.objects.count(), 1)
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 3)
        self.assertEqual(sale.total, 115000)
        self.assertContains(self.client.get(reverse("sale_list")), "115000")
        self.assertContains(self.client.get(reverse("receipt", args=[sale.pk])), "چاپ رسید")

    def test_product_and_stock_management_and_csrf(self):
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.post(reverse("product_new"), {
            "name": "محصول جدید", "sku": "lower-34", "barcode": "1234567",
            "price": 2000, "active": "on", "category": "نمونه", "description": "ساده",
        }), reverse("products"))
        product = Product.objects.get(sku="LOWER-34")
        self.assertRedirects(self.client.post(reverse("add_stock", args=[product.pk]), {
            "quantity": 7, "reason": "ورودی",
        }), reverse("products"))
        product.refresh_from_db()
        self.assertEqual(product.stock, 7)
        self.assertEqual(StockMovement.objects.get(product=product).delta, 7)
        hardened_client = Client(enforce_csrf_checks=True)
        self.assertEqual(hardened_client.post(reverse("login"), {
            "username": settings.STORE_MANAGER_EMAIL, "password": self.password,
        }).status_code, 403)
