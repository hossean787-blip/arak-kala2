from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView
from django.urls import path
from store import api, views

urlpatterns = [
    path("", api.storefront, name="home"),
    path("shop/home/", views.home, name="classic_home"),
    path("api/health", api.health),
    path("api/products", api.public_products),
    path("api/products/<int:pk>", api.public_products),
    path("api/auth/register", api.customer_register),
    path("api/auth/login", api.customer_login),
    path("api/auth/logout", api.customer_logout),
    path("api/me", api.current_customer),
    path("api/orders", api.customer_orders),
    path("api/admin/session", api.manager_login),
    path("api/admin/logout", api.manager_logout),
    path("api/admin/products", api.manager_products),
    path("api/admin/products/<int:pk>", api.manager_products),
    path("api/admin/images", api.manager_image),
    path("api/admin/orders", api.manager_orders),
    path("api/admin/orders/<int:pk>/status", api.manager_order_status),
    path("api/admin/stats", api.manager_stats),
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

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
