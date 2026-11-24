from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Order, Product, StockMovement
from .services import increase_stock, place_order, reserve_product


class OrderServiceRegressionTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(sku="STAB-1", name="Regression", price=1000, stock=5)

    def order(self, token, cart):
        return place_order(token, "Test customer", "09120000000", "Test address", cart)

    def test_replay_must_have_same_cart(self):
        token = uuid4()
        first = self.order(token, {self.product.pk: 2})
        self.assertEqual(self.order(token, {self.product.pk: 2}).pk, first.pk)
        with self.assertRaises(ValidationError):
            self.order(token, {self.product.pk: 3})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_empty_and_invalid_quantities_do_not_mutate(self):
        for cart in ({}, {self.product.pk: 0}, {self.product.pk: -1}, {self.product.pk: True}):
            with self.subTest(cart=cart), self.assertRaises(ValidationError):
                self.order(uuid4(), cart)
        for quantity in (-1, 0, True):
            with self.assertRaises(ValidationError):
                reserve_product(self.product.pk, quantity)
            with self.assertRaises(ValidationError):
                increase_stock(self.product, quantity, "invalid")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)
