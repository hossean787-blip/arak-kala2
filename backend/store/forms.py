from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import MAX_STOCK, MAX_UNIT_PRICE, Customer, Order, Product

DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class ManagerAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="ایمیل مدیر", widget=forms.EmailInput(attrs={
        "autocomplete": "username", "dir": "ltr",
    }))
    password = forms.CharField(label="رمز عبور", strip=False, widget=forms.PasswordInput(attrs={
        "autocomplete": "current-password",
    }))
    error_messages = {
        "invalid_login": "ایمیل یا رمز عبور درست نیست.",
        "inactive": "حساب در دسترس نیست.",
    }

    def clean_username(self):
        username = self.cleaned_data["username"].lower()
        if username != settings.STORE_MANAGER_EMAIL:
            raise self.get_invalid_login_error()
        return username


class ProductForm(forms.ModelForm):
    price = forms.IntegerField(label="قیمت فروش به ریال", min_value=0, max_value=MAX_UNIT_PRICE)
    discount_price = forms.IntegerField(label="قیمت با تخفیف به ریال",
                                        min_value=0, max_value=MAX_UNIT_PRICE, required=False)

    class Meta:
        model = Product
        fields = ("name", "sku", "barcode", "category", "description", "price", "discount_price", "active")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean_sku(self):
        return self.cleaned_data["sku"].strip().upper()

    def clean_barcode(self):
        return self.cleaned_data["barcode"].strip()

    def clean(self):
        super().clean()
        price = self.cleaned_data.get("price")
        discount = self.cleaned_data.get("discount_price")
        if price is not None and discount is not None and discount >= price:
            self.add_error("discount_price", "قیمت با تخفیف باید از قیمت فروش کمتر باشد.")


class StockForm(forms.Form):
    quantity = forms.IntegerField(label="تعداد ورودی", min_value=1, max_value=MAX_STOCK)
    reason = forms.CharField(label="شرح", max_length=150)


class SaleForm(forms.Form):
    token = forms.UUIDField(widget=forms.HiddenInput())
    customer = forms.CharField(label="نام خریدار", max_length=150, required=False)


class LineForm(forms.Form):
    product = forms.ModelChoiceField(label="کالا", queryset=Product.objects.none())
    quantity = forms.IntegerField(label="تعداد", min_value=1, max_value=MAX_STOCK)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(active=True).order_by("name", "pk")


class SaleLineFormSet(forms.BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        if not any(form.cleaned_data for form in self.forms):
            raise ValidationError("دست‌کم یک ردیف کالا وارد کنید.")


class CartLineForm(forms.Form):
    product = forms.IntegerField(min_value=1)
    quantity = forms.IntegerField(label="تعداد", min_value=0, max_value=1000)


class MobileField(forms.RegexField):
    def __init__(self):
        super().__init__(r"09[0-9]{9}\Z", label="شماره موبایل", max_length=11,
                         widget=forms.TextInput(attrs={"inputmode": "tel", "dir": "ltr"}),
                         error_messages={"invalid": "شماره موبایل ۱۱ رقمی با ۰۹ شروع می‌شود."})

    def to_python(self, value):
        return super().to_python(value).translate(DIGITS)


class CustomerLoginForm(AuthenticationForm):
    username = forms.CharField(label="موبایل یا نام کاربری", max_length=30)
    password = forms.CharField(label="رمز عبور", strip=False, widget=forms.PasswordInput)

    def clean_username(self):
        identity = self.cleaned_data["username"].lower().translate(DIGITS)
        return Customer.objects.filter(Q(phone=identity) | Q(alias=identity)).values_list(
            "account__username", flat=True
        ).first() or ""


class CustomerRegistrationForm(forms.Form):
    name = forms.CharField(label="نام و نام خانوادگی", max_length=150)
    phone = MobileField()
    alias = forms.RegexField(r"[a-zA-Z][a-zA-Z0-9_]{2,29}\Z", label="نام کاربری اختیاری",
                             required=False, max_length=30,
                             help_text="با حرف انگلیسی شروع شود و دست‌کم ۳ نویسه داشته باشد.")
    password = forms.CharField(label="رمز عبور", strip=False, widget=forms.PasswordInput,
                               validators=[validate_password])

    def clean_alias(self):
        return self.cleaned_data["alias"].lower() or None


class CheckoutForm(forms.ModelForm):
    phone = MobileField()

    class Meta:
        model = Order
        fields = ("customer", "phone", "address")
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}


class TrackingForm(forms.Form):
    code = forms.CharField(label="کد پیگیری", max_length=20)
    phone = MobileField()
