from django.contrib.auth.views import LogoutView
from django.urls import path
from store import views

urlpatterns = [
    path("", views.home, name="home"),
    path("shop/", views.catalog, name="catalog"),
    path("shop/products/<int:pk>/", views.product_detail, name="product_detail"),
    path("shop/cart/", views.cart, name="cart"),
    path("shop/cart/update/", views.change_cart, name="change_cart"),
    path("shop/checkout/", views.checkout, name="checkout"),
    path("shop/order/complete/", views.order_done, name="order_done"),
    path("shop/track/", views.track, name="track"),
    path("shop/account/login/", views.CustomerLogin.as_view(), name="customer_login"),
    path("shop/account/register/", views.customer_register, name="customer_register"),
    path("shop/account/orders/", views.customer_orders, name="customer_orders"),
    path("manager/login/", views.ManagerLogin.as_view(), name="login"),
    path("manager/logout/", LogoutView.as_view(), name="logout"),
    path("manager/", views.dashboard, name="dashboard"),
    path("manager/products/", views.products, name="products"),
    path("manager/products/new/", views.product_edit, name="product_new"),
    path("manager/products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("manager/products/<int:pk>/stock/", views.add_stock, name="add_stock"),
    path("pos/", views.pos, name="pos"),
    path("manager/orders/", views.orders, name="orders"),
    path("manager/orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("manager/sales/", views.sale_list, name="sale_list"),
    path("manager/sales/<int:pk>/", views.receipt, name="receipt"),
]
