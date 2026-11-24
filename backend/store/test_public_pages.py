from django.test import TestCase, Client
from django.urls import reverse
from .models import Product, SavedAddress, Customer

class PublicPagesTests(TestCase):
    def setUp(self):
        self.item=Product.objects.create(sku="MULTIPAGE-TEST",name="کالای چندصفحه‌ای",category="نمونه",stock=4,price=1200)

    def test_routes_cart_favorites(self):
        for path in ["/","/products/","/categories/","/search/","/favorites/","/cart/","/login/","/register/","/tracking/","/about/","/contact/","/terms/","/privacy/",f"/products/{self.item.pk}/"]:
            self.assertEqual(self.client.get(path).status_code,200,path)
        self.client.post(reverse("toggle_favorite",args=[self.item.pk]))
        self.assertContains(self.client.get("/favorites/"),self.item.name)
        self.client.post(reverse("change_cart"),{"product":self.item.pk,"quantity":2})
        self.assertContains(self.client.get("/cart/"),self.item.name)
        self.assertContains(self.client.get("/checkout/"),"ثبت سفارش آزمایشی")
        self.assertEqual(self.client.post("/cart/import/",data=[{"id":self.item.pk,"quantity":3}],content_type="application/json").status_code,200)
        self.assertEqual(self.client.session["cart"][str(self.item.pk)],3)
        self.client.post("/cart/import/",data=[{"id":self.item.pk,"quantity":3}],content_type="application/json")
        self.assertEqual(self.client.session["cart"][str(self.item.pk)],3)

    def test_address_ownership(self):
        first=Client()
        second=Client()
        for client,phone in [(first,"09120000111"),(second,"09120000222")]:
            response=client.post("/register/",{"name":"خریدار آزمون","phone":phone,"alias":"","password":"Test-only-"+phone+"-phrase!"})
            self.assertEqual(response.status_code,302)
        response=first.post("/account/addresses/",{"title":"خانه","recipient":"خریدار آزمون","phone":"09120000111","address":"نشانی تست اول"})
        self.assertEqual(response.status_code,302)
        address=SavedAddress.objects.get()
        self.assertEqual(second.get(reverse("edit_address",args=[address.pk])).status_code,404)
        self.assertEqual(second.post(reverse("remove_address",args=[address.pk])).status_code,404)
        self.assertTrue(SavedAddress.objects.filter(pk=address.pk).exists())
        self.assertContains(first.get("/account/addresses/"),address.address)
        self.assertNotContains(second.get("/account/addresses/"),address.address)
        first.post(reverse("change_cart"),{"product":self.item.pk,"quantity":1})
        self.assertContains(first.get("/checkout/",{"address":address.pk}),address.address)


    def test_catalog_filters_related_and_sitemap(self):
        deal=Product.objects.create(sku="CAT-DEAL",name="کالای تخفیف نمونه",category="نمونه",stock=2,price=2000,discount_price=900)
        hidden=Product.objects.create(sku="CAT-HIDDEN",name="مخفی آزمایشی",category="نمونه",stock=9,price=1,active=False)
        sold=Product.objects.create(sku="CAT-SOLD",name="ناموجود آزمایشی",category="نمونه",stock=0,price=500)
        r=self.client.get("/products/",{"available":"1","discounted":"1","max_price":"1000"})
        self.assertEqual(list(r.context["page"].object_list),[deal])
        r=self.client.get("/products/",{"min_price":"3000","max_price":"1000"})
        self.assertTrue(r.context["filter_errors"])
        r=self.client.get(reverse("public_product",args=[self.item.pk]))
        self.assertEqual(list(r.context["related"]),[deal])
        self.assertContains(r,'rel="canonical"')
        sitemap=self.client.get("/sitemap.xml")
        self.assertContains(sitemap,reverse("public_product",args=[deal.pk]))
        self.assertNotContains(sitemap,reverse("public_product",args=[hidden.pk]))
        self.assertContains(self.client.get("/robots.txt"),"Disallow: /manager/")

    def test_favorite_persistence_and_account_isolation(self):
        from django.contrib.auth import get_user_model
        from .models import Favorite
        from uuid import uuid4
        first=Client()
        first.post(reverse("toggle_favorite",args=[self.item.pk]),{"action":"add"})
        phrase=uuid4().hex
        first.post("/register/",{"name":"خریدار","phone":"09120000333","alias":"","password":phrase})
        customer=Customer.objects.get(phone="09120000333")
        self.assertTrue(Favorite.objects.filter(customer=customer,product=self.item).exists())
        second=Client()
        second.force_login(customer.account)
        self.assertContains(second.get("/favorites/"),self.item.name)
        second.post(reverse("toggle_favorite",args=[self.item.pk]),{"action":"add"})
        self.assertEqual(Favorite.objects.filter(customer=customer).count(),1)
        other=get_user_model().objects.create_user(username="fixture-other",password=uuid4().hex)
        Customer.objects.create(account=other,name="دیگر",phone="09120000444")
        stranger=Client()
        stranger.force_login(other)
        self.assertNotContains(stranger.get("/favorites/"),self.item.name)
        second.post(reverse("toggle_favorite",args=[self.item.pk]),{"action":"remove"})
        self.assertFalse(Favorite.objects.filter(customer=customer).exists())
