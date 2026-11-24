"""Customer-only profile and verified-email recovery, never manager recovery."""
import hashlib
import logging
import re
from datetime import timedelta
from secrets import token_urlsafe
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth.views import PasswordResetConfirmView, redirect_to_login
from django.core.mail import send_mail
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .models import Customer, Order
from .public_views import get_customer

logger=logging.getLogger(__name__)
COOLDOWN=timedelta(seconds=120)
VERIFY_TTL=timedelta(minutes=30)

class ProfileForm(forms.ModelForm):
    name=forms.CharField(label="نام و نام خانوادگی",max_length=150)
    alias=forms.RegexField(r"[a-zA-Z][a-zA-Z0-9_]{2,29}\Z",label="نام کاربری اختیاری",required=False,max_length=30)
    current_password=forms.CharField(label="رمز عبور فعلی",strip=False,widget=forms.PasswordInput(attrs={"autocomplete":"current-password"}))
    class Meta:
        model=Customer
        fields=("name","alias")
    def clean_alias(self):
        return self.cleaned_data["alias"].lower() or None
    def clean_current_password(self):
        value=self.cleaned_data["current_password"]
        if not self.instance.account.check_password(value):
            raise forms.ValidationError("رمز عبور فعلی درست نیست.")
        return value

class RecoveryForm(forms.Form):
    email=forms.EmailField(label="ایمیل بازیابی",max_length=254,widget=forms.EmailInput(attrs={"autocomplete":"email","dir":"ltr"}))
    current_password=forms.CharField(label="رمز عبور فعلی",strip=False,widget=forms.PasswordInput(attrs={"autocomplete":"current-password"}))
    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

class ForgotForm(forms.Form):
    email=forms.EmailField(label="ایمیل تأییدشده حساب",max_length=254,widget=forms.EmailInput(attrs={"autocomplete":"email","dir":"ltr"}))
    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

class CustomerTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self,user,timestamp):
        # Bind reset token to the verified recovery address as well as password.
        email=Customer.objects.filter(account=user).values_list("recovery_email",flat=True).first() or ""
        return super()._make_hash_value(user,timestamp)+email

tokens=CustomerTokenGenerator()

def form_page(request,title,form,submit,**context):
    return render(request,"store/account_security.html",{"title":title,"form":form,"submit":submit,"sensitive_page":True,**context})

def send_recovery_mail(subject,body,recipient):
    try:
        return send_mail(subject,body,settings.DEFAULT_FROM_EMAIL,[recipient],fail_silently=False)==1
    except Exception:
        # Avoid logging email, token, SMTP credentials or provider exception details.
        logger.warning("Customer recovery email delivery failed")
        return False

@never_cache
@require_http_methods(["GET","POST"])
def profile(request):
    customer=get_customer(request)
    if customer is None:
        return redirect_to_login(request.path,reverse("public_login"))
    form=ProfileForm(request.POST if request.method=="POST" else None,instance=customer)
    if request.method=="POST" and form.is_valid():
        try:
            with transaction.atomic():
                customer.save(update_fields=["name","alias"])
        except IntegrityError:
            form.add_error("alias","نام کاربری در دسترس نیست.")
        else:
            messages.success(request,"پروفایل ذخیره شد.")
            return redirect("account")
    return form_page(request,"ویرایش پروفایل",form,"ذخیره تغییرات",note="شماره موبایل ورود از این بخش قابل تغییر نیست.")

@never_cache
@require_http_methods(["GET","POST"])
def change_password(request):
    customer=get_customer(request)
    if customer is None:
        return redirect_to_login(request.path,reverse("public_login"))
    form=PasswordChangeForm(request.user,request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            user=form.save()
            Customer.objects.filter(pk=customer.pk).update(pending_email="",verification_digest="",verification_expires=None)
        update_session_auth_hash(request,user)
        messages.success(request,"رمز عبور تغییر کرد؛ نشست‌های قبلی دیگر معتبر نیستند.")
        return redirect("account")
    return form_page(request,"تغییر رمز عبور",form,"تغییر رمز")

@never_cache
@require_http_methods(["GET","POST"])
def recovery_email(request):
    customer=get_customer(request)
    if customer is None:
        return redirect_to_login(request.path,reverse("public_login"))
    form=RecoveryForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        if not settings.ARAK_MAIL_ENABLED:
            form.add_error(None,"ارسال ایمیل بازیابی هنوز فعال نشده است.")
        elif not request.user.check_password(form.cleaned_data["current_password"]):
            form.add_error("current_password","رمز عبور فعلی درست نیست.")
        else:
            email=form.cleaned_data["email"]
            now=timezone.now()
            with transaction.atomic():
                locked=Customer.objects.select_for_update().get(pk=customer.pk)
                if locked.verification_sent_at and now-locked.verification_sent_at<COOLDOWN:
                    form.add_error(None,"برای ارسال مجدد کمی صبر کنید.")
                else:
                    token=token_urlsafe(32)
                    locked.pending_email=email
                    locked.verification_digest=hashlib.sha256(token.encode()).hexdigest()
                    locked.verification_expires=now+VERIFY_TTL
                    locked.verification_sent_at=now
                    locked.save(update_fields=["pending_email","verification_digest","verification_expires","verification_sent_at"])
            if not form.errors:
                link=settings.ARAK_PUBLIC_ORIGIN+reverse("verify_email",args=[token])
                if send_recovery_mail("تأیید ایمیل بازیابی اراک کالا","برای تأیید ایمیل تا ۳۰ دقیقه وارد حساب خود شوید و این پیوند را باز کنید:\n"+link,email):
                    messages.success(request,"پیوند تأیید به ایمیل ارسال شد.")
                    return redirect("recovery_email")
                # Invalidate undelivered link; cooldown still applies.
                Customer.objects.filter(pk=customer.pk,verification_digest=hashlib.sha256(token.encode()).hexdigest()).update(pending_email="",verification_digest="",verification_expires=None)
                form.add_error(None,"ارسال ایمیل موفق نبود؛ بعداً دوباره تلاش کنید.")
    return form_page(request,"ایمیل بازیابی",form,"ارسال پیوند تأیید",note="ایمیل فقط پس از تأیید مالکیت فعال می‌شود.",mail_disabled=not settings.ARAK_MAIL_ENABLED,verified_email=customer.recovery_email)

@never_cache
@require_http_methods(["GET","POST"])
def verify_email(request,token):
    customer=get_customer(request)
    if customer is None:
        return redirect_to_login(request.path,reverse("public_login"))
    digest=hashlib.sha256(token.encode()).hexdigest() if re.fullmatch(r"[A-Za-z0-9_-]{43}",token) else ""
    valid=bool(digest and customer.pending_email and customer.verification_expires and customer.verification_expires>timezone.now() and constant_time_compare(digest,customer.verification_digest))
    if request.method=="POST" and valid:
        try:
            with transaction.atomic():
                locked=Customer.objects.select_for_update().get(pk=customer.pk)
                if not locked.verification_expires or locked.verification_expires<=timezone.now() or not constant_time_compare(digest,locked.verification_digest):
                    raise ValueError("expired")
                locked.recovery_email=locked.pending_email
                locked.pending_email=""
                locked.verification_digest=""
                locked.verification_expires=None
                locked.save(update_fields=["recovery_email","pending_email","verification_digest","verification_expires"])
        except (IntegrityError,ValueError):
            valid=False
        else:
            messages.success(request,"ایمیل بازیابی تأیید شد.")
            return redirect("account")
    return render(request,"store/verify_recovery.html",{"valid":valid,"sensitive_page":True})

@never_cache
@require_http_methods(["GET","POST"])
def forgot_password(request):
    form=ForgotForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and form.is_valid():
        if settings.ARAK_MAIL_ENABLED:
            now=timezone.now()
            with transaction.atomic():
                customer=Customer.objects.select_for_update().select_related("account").filter(recovery_email=form.cleaned_data["email"],account__is_active=True).first()
                allowed=bool(customer and customer.account.has_usable_password() and (not customer.reset_sent_at or now-customer.reset_sent_at>=COOLDOWN))
                if allowed:
                    customer.reset_sent_at=now
                    customer.save(update_fields=["reset_sent_at"])
            if allowed:
                uid=urlsafe_base64_encode(force_bytes(customer.account_id))
                link=settings.ARAK_PUBLIC_ORIGIN+reverse("reset_confirm",args=[uid,tokens.make_token(customer.account)])
                send_recovery_mail("بازیابی رمز عبور اراک کالا","پیوند تغییر رمز تا ۳۰ دقیقه معتبر است:\n"+link,customer.recovery_email)
        # Same response for known/unknown/disabled/failed mail. No disclosure.
        return redirect("reset_sent")
    return form_page(request,"بازیابی رمز عبور",form,"درخواست بازیابی",note="از ایمیل بازیابی تأییدشده استفاده کنید.",mail_disabled=not settings.ARAK_MAIL_ENABLED)

@never_cache
def reset_sent(request):
    return render(request,"store/security_message.html",{"title":"درخواست دریافت شد","message":"اگر ایمیل تأییدشده‌ای وجود داشته باشد و ارسال فعال باشد، پیوند بازیابی برای آن ارسال می‌شود.","sensitive_page":True})

class CustomerResetConfirm(PasswordResetConfirmView):
    template_name="store/reset_confirm.html"
    success_url=reverse_lazy("reset_complete")
    token_generator=tokens
    form_class=SetPasswordForm
    post_reset_login=False
    extra_context={"sensitive_page":True}
    def get_user(self,uidb64):
        user=super().get_user(uidb64)
        if user is None or not user.is_active or not Customer.objects.filter(account=user,recovery_email__isnull=False).exclude(recovery_email="").exists():
            return None
        return user
    def form_valid(self,form):
        with transaction.atomic():
            # Revalidate inside lock to stop two simultaneous token replays.
            customer=Customer.objects.select_for_update().select_related("account").get(account=self.user)
            from django.contrib.auth.views import INTERNAL_RESET_SESSION_TOKEN
            if not tokens.check_token(customer.account,self.request.session.get(INTERNAL_RESET_SESSION_TOKEN,"")):
                form.add_error(None,"پیوند بازیابی دیگر معتبر نیست.")
                return self.form_invalid(form)
            response=super().form_valid(form)
            Customer.objects.filter(pk=customer.pk).update(pending_email="",verification_digest="",verification_expires=None)
            return response

@never_cache
def reset_complete(request):
    return render(request,"store/security_message.html",{"title":"رمز عبور تغییر کرد","message":"اکنون با رمز عبور جدید وارد حساب خود شوید.","sensitive_page":True})

@never_cache
def order_detail(request,pk):
    customer=get_customer(request)
    if customer is None:
        return redirect_to_login(request.path,reverse("public_login"))
    order=get_object_or_404(Order.objects.prefetch_related("lines"),pk=pk,account=customer)
    return render(request,"store/customer_order_detail.html",{"order":order,"sandbox_enabled":settings.ARAK_SANDBOX_PAYMENTS})
