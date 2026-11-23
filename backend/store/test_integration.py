import base64
import json
from io import BytesIO
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from PIL import Image

from .models import ManagerToken, Order, Product, StockMovement


class ShopIntegrationTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        override = self.settings(MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)
        self.password = "Integration-password42#"
        self.manager = get_user_model().objects.create_user(
            settings.STORE_MANAGER_EMAIL, email=settings.STORE_MANAGER_EMAIL, password=self.password,
        )
        self.app = Client(enforce_csrf_checks=True)
        self.web = Client(enforce_csrf_checks=True)
        self.web.get("/")

    def request(self, client, method, path, data=None, token=None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if "csrftoken" in client.cookies:
            headers["X-CSRFToken"] = client.cookies["csrftoken"].value
        return client.generic(method, path, json.dumps(data) if data is not None else "",
                              content_type="application/json", headers=headers)

    def manager_login(self):
        response = self.request(self.app, "POST", "/api/admin/session",
                                {"email": self.manager.email, "password": self.password})
        self.assertEqual(response.status_code, 200, response.content)
        token = response.json()["token"]
        self.assertFalse(ManagerToken.objects.filter(digest=token).exists())
        return token

    def register(self, web=None, phone="09120000000"):
        web = web or self.web
        response = self.request(web, "POST", "/api/auth/register", {
            "name": "مشتری آزمایشی", "phone": phone, "alias": "", "password": "Example-42-passphrase",
        })
        self.assertEqual(response.status_code, 201, response.content)

    def test_product_image_order_and_stock_are_shared(self):
        token = self.manager_login()
        sample = BytesIO()
        Image.new("RGB", (8, 8), "white").save(sample, "PNG")
        photo = self.request(self.app, "POST", "/api/admin/images", {
            "mime": "image/png", "base64": base64.b64encode(sample.getvalue()).decode(),
        }, token)
        self.assertEqual(photo.status_code, 201, photo.content)
        url = photo.json()["url"]
        created = self.request(self.app, "POST", "/api/admin/products", {
            "name": "کالای آزمون", "category": "آزمایشی", "price": 1051,
            "stock": 3, "images": [url],
        }, token)
        self.assertEqual(created.status_code, 201, created.content)
        product_id = created.json()["id"]
        product = self.web.get(f"/api/products/{product_id}").json()
        self.assertEqual((product["price"], product["stock"], product["images"]), (1051, 3, [url]))
        self.assertContains(self.web.get("/shop/"), product["name"])
        self.register()
        order_data = {"token": str(uuid4()), "full_name": "خریدار آزمایشی",
                      "phone": "09120000000", "address": "نشانی آزمایشی مشتری",
                      "items": [{"product_id": product_id, "quantity": 2}]}
        order = self.request(self.web, "POST", "/api/orders", order_data)
        self.assertEqual(order.status_code, 201, order.content)
        order_id = order.json()["order_id"]
        self.assertEqual(order.json()["total"], 2102)
        self.assertEqual(self.request(self.web, "POST", "/api/orders", order_data).json()["order_id"], order_id)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Product.objects.get(pk=product_id).stock, 1)
        self.assertEqual(self.request(self.app, "GET", "/api/admin/orders", token=token)
                         .json()["orders"][0]["id"], order_id)
        other = Client(enforce_csrf_checks=True)
        other.get("/")
        self.register(other, "09120000001")
        self.assertEqual(other.get("/api/orders").json()["orders"], [])
        conflict = self.request(self.app, "PATCH", f"/api/admin/products/{product_id}",
                                {"stock": 7, "expected_stock": 3}, token)
        self.assertEqual(conflict.status_code, 409)
        for _ in range(2):
            cancelled = self.request(self.app, "PATCH", f"/api/admin/orders/{order_id}/status",
                                     {"status": "cancelled"}, token)
            self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(Product.objects.get(pk=product_id).stock, 3)
        self.assertEqual(list(StockMovement.objects.filter(product_id=product_id)
                              .order_by("pk").values_list("delta", flat=True)), [3, -2, 2])
        self.assertEqual(self.request(self.app, "DELETE", f"/api/admin/products/{product_id}",
                                      token=token).status_code, 200)
        self.assertEqual(self.web.get(f"/api/products/{product_id}").status_code, 404)

    def test_manager_access_and_csrf(self):
        self.assertEqual(self.web.get("/api/admin/products").status_code, 401)
        self.assertEqual(self.web.post("/api/auth/register", data="{}",
                                       content_type="application/json").status_code, 403)
        self.register()
        self.assertEqual(self.web.get("/api/admin/stats").status_code, 401)
        self.assertNotContains(self.web.get("/"), "/manager/")
        browser_manager = Client()
        browser_manager.force_login(self.manager)
        self.assertEqual(browser_manager.get("/api/admin/products").status_code, 401)
        token = self.manager_login()
        self.assertEqual(self.request(self.app, "POST", "/api/admin/logout", token=token).status_code, 200)
        self.assertEqual(self.request(self.app, "GET", "/api/admin/products", token=token).status_code, 401)

    def test_legacy_product_and_account_work_on_new_storefront(self):
        product = Product.objects.create(sku="OLD-1", name="کالای قبلی", price=1000,
                                         discount_price=901, stock=2)
        self.register()
        self.assertEqual(self.request(self.web, "POST", "/api/auth/logout").status_code, 200)
        logged_in = self.request(self.web, "POST", "/api/auth/login", {
            "username": "۰۹۱۲۰۰۰۰۰۰۰", "password": "Example-42-passphrase",
        })
        self.assertEqual(logged_in.status_code, 200, logged_in.content)
        self.assertEqual(self.web.get(f"/api/products/{product.pk}").json()["price"], 901)
        self.assertEqual(self.web.get(f"/api/products/{product.pk}").json()["images"], [])
