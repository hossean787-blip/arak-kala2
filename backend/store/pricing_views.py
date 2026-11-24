from django import forms
from django.contrib import messages
from django.db import IntegrityError,transaction
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.http import require_http_methods
from .views import manager_only
from .models import Coupon,ShippingMethod,MAX_UNIT_PRICE

class CouponForm(forms.ModelForm):
    code=forms.RegexField(r"[A-Za-z0-9_-]{3,32}\Z",label="کد تخفیف")
    amount=forms.IntegerField(label="تخفیف ثابت به ریال",min_value=1,max_value=MAX_UNIT_PRICE)
    minimum=forms.IntegerField(label="حداقل مبلغ خرید",min_value=0,max_value=MAX_UNIT_PRICE)
    max_uses=forms.IntegerField(label="سقف دفعات استفاده",min_value=1,max_value=100000)
    def clean_code(self):
        return self.cleaned_data["code"].upper()
    class Meta:
        model=Coupon
        fields=("code","amount","minimum","max_uses","active")

class ShippingForm(forms.ModelForm):
    fee=forms.IntegerField(label="هزینه ارسال به ریال",min_value=0,max_value=MAX_UNIT_PRICE)
    class Meta:
        model=ShippingMethod
        fields=("name","fee","active")

def manage(request,pk,model,form_class,title,route):
    obj=get_object_or_404(model,pk=pk) if pk is not None else None
    form=form_class(request.POST if request.method=="POST" else None,instance=obj)
    if request.method=="POST" and form.is_valid():
        try:
            with transaction.atomic(): form.save()
        except IntegrityError: form.add_error(None,"این مقدار قبلاً ثبت شده است.")
        else:
            messages.success(request,"تنظیمات ذخیره شد.")
            return redirect(route)
    return render(request,"store/pricing_management.html",{"form":form,"items":model.objects.all(),"title":title,"is_coupon":model is Coupon})

@manager_only
@require_http_methods(["GET","POST"])
def coupons(request,pk=None):
    return manage(request,pk,Coupon,CouponForm,"کدهای تخفیف","manager_coupons")

@manager_only
@require_http_methods(["GET","POST"])
def shipping(request,pk=None):
    return manage(request,pk,ShippingMethod,ShippingForm,"روش‌های ارسال","manager_shipping")
