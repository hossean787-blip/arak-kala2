from unittest.mock import patch
from uuid import uuid4
from django.test import Client,TestCase,override_settings
from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import reverse
from .models import Customer,Product,Order,SandboxPayment,ReturnRequest
from .services import place_order
from .sandbox_gateway import GatewayError

class AfterSalesTests(TestCase):
    def setUp(self):
        account=get_user_model().objects.create_user(username="after-sales-fixture",password=uuid4().hex)
        self.customer=Customer.objects.create(account=account,name="مشتری",phone="09120000911")
        self.client.force_login(account)
        product=Product.objects.create(sku="AFTER-FIXTURE",name="کالا",price=2000,stock=2)
        self.order=place_order(uuid4(),"مشتری",self.customer.phone,"نشانی آزمون",{product.pk:1},self.customer)
        self.start=reverse("sandbox_start",args=[self.order.pk])
        self.result=reverse("sandbox_result",args=[self.order.pk])
        self.callback=reverse("sandbox_callback",args=[self.order.pk])
    def test_disabled_by_default_and_private_receipt(self):
        self.assertEqual(self.client.post(self.start).status_code,404)
        self.assertContains(self.client.get(reverse("customer_receipt",args=[self.order.pk])),"فاکتور رسمی مالیاتی")
        self.assertEqual(Client().get(reverse("customer_receipt",args=[self.order.pk])).status_code,404)
    @override_settings(ARAK_SANDBOX_PAYMENTS=True,ARAK_PUBLIC_ORIGIN="https://testserver")
    @patch("store.sandbox_gateway.create_payment",return_value="TEST-AUTHORITY")
    @patch("store.sandbox_gateway.verify_payment",return_value="123456")
    def test_callback_untrusted_verify_and_replay(self,verify,create):
        self.assertEqual(self.client.post(self.start).status_code,302)
        self.assertEqual(self.client.post(self.start).status_code,302)
        create.assert_called_once()
        self.assertEqual(self.client.get(self.callback,{"Authority":"wrong","Status":"OK"}).status_code,404)
        self.assertEqual(self.client.get(self.callback,{"Authority":"TEST-AUTHORITY","Status":"OK"}).status_code,302)
        self.assertFalse(verify.called)
        self.assertEqual(Client().post(self.result).status_code,404)
        self.client.post(self.result,{"amount":1})
        verify.assert_called_once_with(2000,"TEST-AUTHORITY")
        self.assertEqual(SandboxPayment.objects.get().state,SandboxPayment.State.VERIFIED)
        self.client.post(self.result)
        verify.assert_called_once()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,Order.Status.NEW)
    @override_settings(ARAK_SANDBOX_PAYMENTS=True,ARAK_PUBLIC_ORIGIN="https://testserver")
    @patch("store.sandbox_gateway.create_payment",side_effect=GatewayError("uncertain"))
    def test_uncertain_request_not_retried(self,create):
        self.client.post(self.start)
        self.client.post(self.start)
        create.assert_called_once()
        self.assertEqual(SandboxPayment.objects.get().state,SandboxPayment.State.UNKNOWN)
    def test_return_request_owner_and_review_no_stock_or_payment_change(self):
        route=reverse("customer_return",args=[self.order.pk])
        self.client.post(route,{"reason":"نمونه"})
        self.assertFalse(ReturnRequest.objects.exists())
        Order.objects.filter(pk=self.order.pk).update(status=Order.Status.DELIVERED)
        self.client.post(route,{"reason":"نمونه"})
        self.client.post(route,{"reason":"duplicate"})
        item=ReturnRequest.objects.get()
        self.assertEqual(item.reason,"نمونه")
        self.assertEqual(Client().get(route).status_code,404)
        owner=get_user_model().objects.create_user(settings.STORE_MANAGER_EMAIL,email=settings.STORE_MANAGER_EMAIL,password=uuid4().hex)
        manager=Client()
        manager.force_login(owner)
        self.assertRedirects(manager.post(reverse("review_return",args=[item.pk]),{"note":"بررسی آزمایشی"}),"/manager/returns/")
        item.refresh_from_db()
        self.assertEqual(item.state,ReturnRequest.State.REVIEWED)
        self.assertContains(self.client.get(route),"بررسی آزمایشی")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,Order.Status.DELIVERED)
