"""Owner-only web management on the same models and stock ledger as Android."""
import csv
import hashlib
import json
from datetime import timedelta
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from .views import manager_only
from .models import Product, Order, Sale, StockMovement, MAX_STOCK
from .media_service import store_product_image, ImageUploadError, MAX_IMAGE_BYTES
from .services import adjust_stock

def image_version(values):
    return hashlib.sha256(json.dumps(values,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()

@manager_only
@require_http_methods(["GET","POST"])
def images(request,pk):
    product=get_object_or_404(Product,pk=pk)
    if request.method=="POST":
        try:
            with transaction.atomic():
                product=Product.objects.select_for_update().get(pk=pk)
                values=list(product.images)
                if request.POST.get("version")!=image_version(values):
                    raise ValidationError("تصاویر تغییر کرده‌اند؛ صفحه را تازه کنید.")
                action=request.POST.get("action")
                if action=="upload":
                    upload=request.FILES.get("image")
                    if not upload or len(values)>=8:
                        raise ValidationError("یک تصویر انتخاب کنید؛ حداکثر ۸ تصویر مجاز است.")
                    if upload.size>MAX_IMAGE_BYTES:
                        raise ValidationError("حجم تصویر حداکثر ۲ مگابایت است.")
                    values.append(store_product_image(upload.read(MAX_IMAGE_BYTES+1),upload.content_type))
                elif action in {"cover","remove"}:
                    try:
                        index=int(request.POST.get("index",""))
                        if not 0<=index<len(values): raise ValueError
                    except ValueError:
                        raise ValidationError("تصویر معتبر نیست.") from None
                    name=values.pop(index)
                    if action=="cover": values.insert(0,name)
                    # Unlink only; retain storage bytes for rollback and shared references.
                else:
                    raise ValidationError("عملیات معتبر نیست.")
                product.images=values
                product.save(update_fields=["images"])
        except (ValidationError,ImageUploadError) as exc:
            messages.error(request,str(exc))
        else:
            messages.success(request,"تصاویر کالا به‌روزرسانی شد.")
        return redirect("manager_images",pk=pk)
    return render(request,"store/manager_images.html",{"product":product,"version":image_version(product.images)})

class AdjustForm(forms.Form):
    expected=forms.IntegerField(min_value=0,max_value=MAX_STOCK,widget=forms.HiddenInput)
    desired=forms.IntegerField(label="موجودی جدید",min_value=0,max_value=MAX_STOCK)
    reason=forms.CharField(label="دلیل اصلاح موجودی",max_length=150)

@manager_only
@require_http_methods(["GET","POST"])
def stock_adjust(request,pk):
    product=get_object_or_404(Product,pk=pk)
    form=AdjustForm(request.POST if request.method=="POST" else None,initial={"expected":product.stock,"desired":product.stock})
    if request.method=="POST" and form.is_valid():
        try:
            adjust_stock(pk,form.cleaned_data["expected"],form.cleaned_data["desired"],form.cleaned_data["reason"])
        except ValidationError as exc:
            form.add_error(None,exc)
        else:
            messages.success(request,"اصلاح موجودی و گردش آن ثبت شد.")
            return redirect("products")
    return render(request,"store/form.html",{"form":form,"title":"اصلاح موجودی "+product.name})

@manager_only
@require_POST
def visibility(request,pk):
    product=get_object_or_404(Product,pk=pk)
    active=request.POST.get("active")
    if active not in {"1","0"}:
        return HttpResponse("وضعیت نامعتبر",status=400)
    Product.objects.filter(pk=product.pk).update(active=active=="1")
    messages.success(request,"وضعیت نمایش کالا تغییر کرد.")
    return redirect("products")

@manager_only
def inventory(request):
    queryset=StockMovement.objects.select_related("product").order_by("-pk")
    q=request.GET.get("q","").strip()[:100]
    if q: queryset=queryset.filter(Q(product__name__icontains=q)|Q(product__sku__icontains=q))
    return render(request,"store/inventory.html",{"page":Paginator(queryset,50).get_page(request.GET.get("page")),"q":q})

class ReportPeriod(forms.Form):
    start=forms.DateField(label="از تاریخ میلادی",widget=forms.DateInput(attrs={"type":"date"}))
    end=forms.DateField(label="تا تاریخ میلادی",widget=forms.DateInput(attrs={"type":"date"}))
    def clean(self):
        data=super().clean()
        start,end=data.get("start"),data.get("end")
        if start and end and (start>end or (end-start).days>366):
            raise forms.ValidationError("بازه باید معتبر و حداکثر ۳۶۷ روز باشد.")
        return data

def report_data(request):
    end=timezone.localdate()
    defaults={"start":end-timedelta(days=29),"end":end}
    form=ReportPeriod(request.GET if request.GET else None,initial=defaults)
    if request.GET and not form.is_valid(): return form,None
    period=form.cleaned_data if request.GET else defaults
    dates={"created_at__date__gte":period["start"],"created_at__date__lte":period["end"]}
    sales=Sale.objects.filter(**dates)
    orders=Order.objects.filter(**dates)
    values={"pos_count":sales.count(),"pos_total":sales.aggregate(total=Sum("total"))["total"] or 0,
            "order_count":orders.count(),"order_total":orders.exclude(status=Order.Status.CANCELLED).aggregate(total=Sum("total"))["total"] or 0,
            "statuses":list(orders.values("status").annotate(count=Count("pk")).order_by("status")),
            "start":period["start"],"end":period["end"]}
    return form,values

@manager_only
def reports(request):
    form,data=report_data(request)
    return render(request,"store/manager_reports.html",{"form":form,"data":data,"status_labels":dict(Order.Status.choices)})

@manager_only
def export_report(request):
    form,data=report_data(request)
    if data is None: return HttpResponse("Invalid period",status=400)
    response=HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"]='attachment; filename="arak-kala-summary.csv"'
    response.write("\ufeff")
    writer=csv.writer(response)
    writer.writerow(["period_start","period_end","pos_count","pos_total_rial","online_order_count","online_order_value_rial_unpaid"])
    writer.writerow([data["start"],data["end"],data["pos_count"],data["pos_total"],data["order_count"],data["order_total"]])
    return response
