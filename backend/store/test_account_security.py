from urllib.parse import urlsplit
from uuid import uuid4
from django.core import mail
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import Customer, Order, Product
from .account_views import tokens
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

@override_settings(ARAK_MAIL_ENABLED=True, ARAK_PUBLIC_ORIGIN="https://testserver", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="fixture@example.test")
class AccountSecurityTests(TestCase):
    def setUp(self):
        self.phrase=uuid4().hex
        self.client.post("/register/",{"name":"مشتری آزمایشی","phone":"09120000777","alias":"","password":self.phrase})
        self.customer=Customer.objects.get(phone="09120000777")
    def verify(self):
        response=self.client.post("/account/recovery-email/",{"email":"fixture-recovery@example.test","current_password":self.phrase})
        self.assertRedirects(response,"/account/recovery-email/")
        link=urlsplit(mail.outbox[-1].body.splitlines()[-1]).path
        self.assertContains(self.client.get(link),"تأیید ایمیل")
        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.recovery_email)
        self.assertEqual(self.client.post(link).status_code,302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.recovery_email,"fixture-recovery@example.test")
        self.assertContains(self.client.post(link),"پیوند معتبر نیست")
        return link
    def test_verified_recovery_reset_and_replay(self):
        self.verify()
        stranger=Client()
        self.assertRedirects(stranger.post("/password/forgot/",{"email":"fixture-recovery@example.test"}),"/password/sent/")
        link=urlsplit(mail.outbox[-1].body.splitlines()[-1]).path
        count=len(mail.outbox)
        self.assertRedirects(stranger.post("/password/forgot/",{"email":"fixture-recovery@example.test"}),"/password/sent/")
        self.assertRedirects(stranger.post("/password/forgot/",{"email":"missing@example.test"}),"/password/sent/")
        self.assertEqual(len(mail.outbox),count)
        response=stranger.get(link)
        self.assertEqual(response.status_code,302)
        new=uuid4().hex
        self.assertRedirects(stranger.post(response.url,{"new_password1":new,"new_password2":new}),"/password/complete/")
        self.customer.account.refresh_from_db()
        self.assertTrue(self.customer.account.check_password(new))
        self.assertContains(stranger.get(link),"پیوند بازیابی معتبر نیست")
        self.assertEqual(self.client.get("/account/").status_code,302)
    def test_profile_and_password(self):
        self.assertContains(self.client.post("/account/profile/",{"name":"جدید","alias":"newbuyer","current_password":"wrong"}),"درست نیست")
        self.assertRedirects(self.client.post("/account/profile/",{"name":"نام جدید","alias":"newbuyer","current_password":self.phrase}),"/account/")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.alias,"newbuyer")
        self.assertEqual(self.customer.name,"نام جدید")
        second=Client()
        second.force_login(self.customer.account)
        new=uuid4().hex
        self.assertRedirects(self.client.post("/account/password/",{"old_password":self.phrase,"new_password1":new,"new_password2":new}),"/account/")
        self.assertEqual(self.client.get("/account/").status_code,200)
        self.assertEqual(second.get("/account/").status_code,302)
    def test_unverified_and_manager_cannot_reset(self):
        self.client.post("/account/recovery-email/",{"email":"pending@example.test","current_password":self.phrase})
        link=urlsplit(mail.outbox[-1].body.splitlines()[-1]).path
        stranger=Client()
        stranger.post("/register/",{"name":"دیگر","phone":"09120000888","alias":"","password":uuid4().hex})
        self.assertContains(stranger.post(link),"پیوند معتبر نیست")
        before=len(mail.outbox)
        stranger.post("/password/forgot/",{"email":"pending@example.test"})
        self.assertEqual(len(mail.outbox),before)
        Customer.objects.filter(pk=self.customer.pk).update(verification_expires=timezone.now()-timedelta(minutes=1))
        self.assertContains(self.client.post(link),"پیوند معتبر نیست")
        manager=get_user_model().objects.create_user(username="fixture-manager",email="manager@example.test",password=uuid4().hex)
        uid=urlsafe_base64_encode(force_bytes(manager.pk))
        self.assertContains(stranger.get(reverse("reset_confirm",args=[uid,tokens.make_token(manager)])),"پیوند بازیابی معتبر نیست")
    def test_order_detail_is_owner_scoped(self):
        item=Product.objects.create(sku="ACCOUNT-ORDER-FIXTURE",name="کالا",price=100,stock=2)
        self.client.post("/cart/update/",{"product":item.pk,"quantity":1})
        self.client.post("/checkout/",{"customer":"مشتری آزمایشی","phone":self.customer.phone,"address":"نشانی آزمون"})
        order=Order.objects.get()
        self.assertContains(self.client.get(reverse("customer_order_detail",args=[order.pk])),order.code)
        stranger=Client()
        stranger.post("/register/",{"name":"دیگر","phone":"09120000889","alias":"","password":uuid4().hex})
        self.assertEqual(stranger.get(reverse("customer_order_detail",args=[order.pk])).status_code,404)
    @override_settings(ARAK_MAIL_ENABLED=False)
    def test_disabled_mail_never_sends(self):
        self.assertContains(self.client.post("/account/recovery-email/",{"email":"fixture@example.test","current_password":self.phrase}),"فعال نشده")
        self.client.post("/password/forgot/",{"email":"fixture@example.test"})
        self.assertEqual(len(getattr(mail,"outbox",[])),0)
