from django.conf import settings
from django.db import models
from django.db.models import F, Q

MAX_STOCK = 1_000_000
MAX_UNIT_PRICE = 10_000_000_000


class Product(models.Model):
    sku = models.CharField("کد کالا", max_length=40, unique=True)
    barcode = models.CharField("بارکد", max_length=40, blank=True)
    name = models.CharField("نام کالا", max_length=160)
    category = models.CharField("دسته‌بندی", max_length=80, blank=True)
    description = models.TextField("توضیحات", blank=True, max_length=2000)
    price = models.PositiveBigIntegerField("قیمت فروش به ریال")
    discount_price = models.PositiveBigIntegerField("قیمت با تخفیف به ریال", null=True, blank=True)
    stock = models.PositiveIntegerField("موجودی", default=0)
    active = models.BooleanField("فعال برای فروش", default=True)
    images = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["barcode"], condition=~Q(barcode=""),
                                    name="unique_nonblank_barcode"),
            models.CheckConstraint(condition=Q(stock__lte=MAX_STOCK), name="stock_within_limit"),
            models.CheckConstraint(condition=Q(price__lte=MAX_UNIT_PRICE), name="price_within_limit"),
            models.CheckConstraint(condition=Q(discount_price__isnull=True)
                                   | Q(discount_price__lt=F("price")), name="discount_below_price"),
        ]

    @property
    def actual_price(self):
        return self.price if self.discount_price is None else self.discount_price

    def __str__(self):
        return f"{self.name} · {self.sku}"


class Sale(models.Model):
    token = models.UUIDField(unique=True, editable=False)
    fingerprint = models.CharField(max_length=64, editable=False)
    customer = models.CharField("نام خریدار", max_length=150, blank=True)
    total = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class SaleLine(models.Model):
    sale = models.ForeignKey(Sale, related_name="lines", on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    sku = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    quantity = models.PositiveIntegerField()
    unit_price = models.PositiveBigIntegerField()

    @property
    def total(self):
        return self.quantity * self.unit_price


class StockMovement(models.Model):
    product = models.ForeignKey(Product, related_name="movements", on_delete=models.PROTECT)
    sale = models.ForeignKey(Sale, null=True, blank=True, on_delete=models.PROTECT)
    order = models.ForeignKey("Order", null=True, blank=True, on_delete=models.PROTECT)
    delta = models.IntegerField()
    reason = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]


class Customer(models.Model):
    account = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=11, unique=True)
    alias = models.CharField(max_length=30, unique=True, null=True, blank=True)
    recovery_email = models.EmailField(max_length=254, unique=True, null=True, blank=True)
    pending_email = models.EmailField(max_length=254, blank=True, default="")
    verification_digest = models.CharField(max_length=64, blank=True, default="")
    verification_expires = models.DateTimeField(null=True, blank=True)
    verification_sent_at = models.DateTimeField(null=True, blank=True)
    reset_sent_at = models.DateTimeField(null=True, blank=True)


class Coupon(models.Model):
    code = models.CharField("کد تخفیف", max_length=32, unique=True)
    amount = models.PositiveBigIntegerField("تخفیف ثابت به ریال")
    minimum = models.PositiveBigIntegerField("حداقل مبلغ خرید", default=0)
    max_uses = models.PositiveIntegerField("سقف دفعات استفاده", default=1)
    active = models.BooleanField("فعال", default=True)

    class Meta:
        ordering=["code"]


class ShippingMethod(models.Model):
    name = models.CharField("روش ارسال", max_length=80, unique=True)
    fee = models.PositiveBigIntegerField("هزینه ارسال به ریال", default=0)
    active = models.BooleanField("فعال", default=False)

    class Meta:
        ordering=["pk"]


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "در انتظار بررسی"
        CONFIRMED = "confirmed", "تأیید شده"
        SHIPPED = "shipped", "ارسال شده"
        DELIVERED = "delivered", "تحویل شده"
        CANCELLED = "cancelled", "لغو شده"

    token = models.UUIDField(unique=True, editable=False)
    code = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.CharField("نام خریدار", max_length=150)
    phone = models.CharField("موبایل", max_length=11)
    account = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.PROTECT)
    address = models.CharField("نشانی", max_length=700)
    status = models.CharField(max_length=12, choices=Status, default=Status.NEW)
    subtotal = models.PositiveBigIntegerField(default=0)
    discount = models.PositiveBigIntegerField(default=0)
    shipping_fee = models.PositiveBigIntegerField(default=0)
    coupon = models.ForeignKey(Coupon,null=True,blank=True,on_delete=models.PROTECT)
    coupon_code = models.CharField(max_length=32,blank=True,default="")
    shipping_method = models.ForeignKey(ShippingMethod,null=True,blank=True,on_delete=models.PROTECT)
    shipping_name = models.CharField(max_length=80,blank=True,default="")
    total = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class OrderLine(models.Model):
    order = models.ForeignKey(Order, related_name="lines", on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    quantity = models.PositiveIntegerField()
    unit_price = models.PositiveBigIntegerField()

    @property
    def total(self):
        return self.quantity * self.unit_price


class ManagerToken(models.Model):
    digest = models.CharField(max_length=64, unique=True)
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    expires_at = models.DateTimeField(db_index=True)
    auth_hash = models.CharField(max_length=64)


class AuthThrottle(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    window = models.PositiveBigIntegerField(db_index=True)
    count = models.PositiveIntegerField(default=0)


class SavedAddress(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses")
    title = models.CharField("عنوان نشانی", max_length=60)
    recipient = models.CharField("نام گیرنده", max_length=150)
    phone = models.CharField("موبایل", max_length=11)
    address = models.CharField("نشانی کامل", max_length=700)

    class Meta:
        ordering = ["pk"]


class Favorite(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="favorites")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [models.UniqueConstraint(fields=["customer", "product"], name="unique_customer_favorite")]


class SandboxPayment(models.Model):
    class State(models.TextChoices):
        CREATING = "creating", "در حال ایجاد"
        READY = "ready", "آماده آزمون"
        VERIFIED = "verified", "آزمون تأیید شد؛ بدون پرداخت واقعی"
        UNKNOWN = "unknown", "نامشخص؛ نیازمند بررسی"
    order = models.OneToOneField(Order,on_delete=models.PROTECT,related_name="sandbox_payment")
    amount = models.PositiveBigIntegerField()
    authority = models.CharField(max_length=80,unique=True,null=True,blank=True)
    reference = models.CharField(max_length=80,blank=True,default="")
    state = models.CharField(max_length=12,choices=State,default=State.CREATING)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True,blank=True)


class ReturnRequest(models.Model):
    class State(models.TextChoices):
        NEW = "new", "در انتظار بررسی"
        REVIEWED = "reviewed", "بررسی شد؛ بدون تسویه یا مرجوعی خودکار"
    order = models.OneToOneField(Order,on_delete=models.PROTECT,related_name="return_request")
    reason = models.CharField(max_length=700)
    state = models.CharField(max_length=12,choices=State,default=State.NEW)
    manager_note = models.CharField(max_length=700,blank=True,default="")
    created_at = models.DateTimeField(auto_now_add=True)
