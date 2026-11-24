from io import BytesIO
from tempfile import TemporaryDirectory
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image
from .models import Product, StockMovement
from .manager_views import image_version

class ManagementTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        setting=self.settings(MEDIA_ROOT=self.tmp.name)
        setting.enable()
        self.addCleanup(setting.disable)
        self.owner=get_user_model().objects.create_user(settings.STORE_MANAGER_EMAIL,email=settings.STORE_MANAGER_EMAIL,password=uuid4().hex)
        self.client.force_login(self.owner)
        self.product=Product.objects.create(sku="MANAGER-FIXTURE",name="کالای مدیریت",price=4000,stock=4)
    def upload(self,name="photo.png",valid=True):
        buffer=BytesIO()
        Image.new("RGB",(40,80),"white").save(buffer,"PNG")
        return SimpleUploadedFile(name,buffer.getvalue() if valid else b"not an image",content_type="image/png")
    def test_images_shared_and_stale_rejected(self):
        url=reverse("manager_images",args=[self.product.pk])
        old=image_version([])
        self.client.post(url,{"action":"upload","version":old,"image":self.upload()})
        self.product.refresh_from_db()
        self.assertEqual(len(self.product.images),1)
        first=self.product.images[0]
        self.assertEqual(self.client.get("/api/products/"+str(self.product.pk)).json()["images"],[settings.MEDIA_URL+first])
        self.client.post(url,{"action":"upload","version":old,"image":self.upload()})
        self.product.refresh_from_db()
        self.assertEqual(len(self.product.images),1)
        self.client.post(url,{"action":"upload","version":image_version(self.product.images),"image":self.upload(valid=False)})
        self.product.refresh_from_db()
        self.assertEqual(len(self.product.images),1)
        self.client.post(url,{"action":"upload","version":image_version(self.product.images),"image":self.upload()})
        self.product.refresh_from_db()
        second=self.product.images[1]
        self.client.post(url,{"action":"cover","version":image_version(self.product.images),"index":1})
        self.product.refresh_from_db()
        self.assertEqual(self.product.images,[second,first])
        self.client.post(url,{"action":"remove","version":image_version(self.product.images),"index":1})
        self.product.refresh_from_db()
        self.assertEqual(self.product.images,[second])
    def test_stock_conflict_and_ledger(self):
        path=reverse("stock_adjust",args=[self.product.pk])
        self.client.post(path,{"expected":4,"desired":2,"reason":"اصلاح آزمون"})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock,2)
        self.assertEqual(StockMovement.objects.get(product=self.product).delta,-2)
        self.client.post(path,{"expected":4,"desired":9,"reason":"قدیمی"})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock,2)
        self.assertEqual(StockMovement.objects.filter(product=self.product).count(),1)
        self.assertContains(self.client.get("/manager/inventory/"),"اصلاح آزمون")
    def test_filters_visibility_and_report(self):
        self.assertContains(self.client.get("/manager/products/?status=low"),self.product.name)
        self.client.post(reverse("manager_visibility",args=[self.product.pk]),{"active":"0"})
        self.assertEqual(self.client.get("/api/products/"+str(self.product.pk)).status_code,404)
        self.assertContains(self.client.get("/manager/products/?status=inactive"),self.product.name)
        self.assertContains(self.client.get("/manager/reports/"),"نه درآمد وصول")
        response=self.client.get("/manager/reports/export/")
        self.assertEqual(response.status_code,200)
        self.assertIn(b"online_order_value_rial_unpaid",response.content)
        self.assertEqual(self.client.get("/manager/reports/export/?start=2026-12-01&end=2026-01-01").status_code,400)
    def test_nonmanager_and_csrf(self):
        stranger=Client()
        stranger.force_login(get_user_model().objects.create_user(username="fixture-stranger",password=uuid4().hex))
        for route in ["/manager/inventory/","/manager/reports/","/manager/reports/export/",reverse("manager_images",args=[self.product.pk]),reverse("stock_adjust",args=[self.product.pk])]:
            self.assertEqual(stranger.get(route).status_code,403)
        csrf=Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(reverse("manager_visibility",args=[self.product.pk]),{"active":"0"}).status_code,403)
