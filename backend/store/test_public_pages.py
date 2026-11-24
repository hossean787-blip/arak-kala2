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
