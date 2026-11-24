"""Order-owner-only sandbox payment, printable order summaries and review requests."""
from django import forms
from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError,transaction
from django.http import Http404
from django.shortcuts import get_object_or_404,redirect,render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods,require_POST
from .models import Order,SandboxPayment,ReturnRequest
from .views import manager_only
from . import sandbox_gateway as gateway

def customer_order(request,pk):
    if not request.user.is_authenticated:
        raise Http404
    return get_object_or_404(Order.objects.prefetch_related("lines"),pk=pk,account__account=request.user)

@never_cache
@require_POST
def start_sandbox(request,pk):
    if not settings.ARAK_SANDBOX_PAYMENTS: raise Http404
    order=customer_order(request,pk)
    with transaction.atomic():
        order=Order.objects.select_for_update().get(pk=order.pk)
        if order.status!=Order.Status.NEW or order.total<=0:
            messages.error(request,"این سفارش برای آزمون درگاه مناسب نیست.")
            return redirect("customer_order_detail",pk=pk)
        attempt,created=SandboxPayment.objects.get_or_create(order=order,defaults={"amount":order.total})
        if not created:
            if attempt.state==SandboxPayment.State.READY and attempt.authority:
                return redirect(gateway.payment_url(attempt.authority))
            return redirect("sandbox_result",pk=pk)
    # External request occurs outside database lock. Never automatically retry an uncertain creation.
    try:
        authority=gateway.create_payment(attempt.amount,settings.ARAK_PUBLIC_ORIGIN+reverse("sandbox_callback",args=[pk]))
        SandboxPayment.objects.filter(pk=attempt.pk,state=SandboxPayment.State.CREATING).update(authority=authority,state=SandboxPayment.State.READY)
    except (gateway.GatewayError,IntegrityError):
        SandboxPayment.objects.filter(pk=attempt.pk,state=SandboxPayment.State.CREATING).update(state=SandboxPayment.State.UNKNOWN)
        messages.error(request,"نتیجه ایجاد تراکنش آزمایشی نامشخص است؛ درخواست جدید خودکار ارسال نمی‌شود.")
        return redirect("sandbox_result",pk=pk)
    return redirect(gateway.payment_url(authority))

@never_cache
@require_http_methods(["GET"])
def sandbox_callback(request,pk):
    if not settings.ARAK_SANDBOX_PAYMENTS: raise Http404
    order=customer_order(request,pk)
    attempt=get_object_or_404(SandboxPayment,order=order)
    # Callback query is untrusted. Do not mark success, and do not render its raw values.
    if not attempt.authority or request.GET.get("Authority")!=attempt.authority:
        raise Http404
    return redirect("sandbox_result",pk=pk)

@never_cache
@require_http_methods(["GET","POST"])
def sandbox_result(request,pk):
    if not settings.ARAK_SANDBOX_PAYMENTS: raise Http404
    order=customer_order(request,pk)
    attempt=get_object_or_404(SandboxPayment,order=order)
    if request.method=="POST" and attempt.authority and attempt.state in (SandboxPayment.State.READY,SandboxPayment.State.UNKNOWN):
        try:
            if order.status!=Order.Status.NEW or order.total!=attempt.amount:
                raise gateway.GatewayError("Order changed")
            reference=gateway.verify_payment(attempt.amount,attempt.authority)
        except gateway.GatewayError:
            SandboxPayment.objects.filter(pk=attempt.pk).exclude(state=SandboxPayment.State.VERIFIED).update(state=SandboxPayment.State.UNKNOWN)
            messages.error(request,"تأیید آزمایشی موفق نبود؛ پرداخت واقعی ثبت نشده است.")
        else:
            with transaction.atomic():
                locked=Order.objects.select_for_update().get(pk=order.pk)
                if locked.status==Order.Status.NEW and locked.total==attempt.amount:
                    SandboxPayment.objects.filter(pk=attempt.pk).exclude(state=SandboxPayment.State.VERIFIED).update(state=SandboxPayment.State.VERIFIED,reference=reference,verified_at=timezone.now())
        return redirect("sandbox_result",pk=pk)
    return render(request,"store/sandbox_result.html",{"order":order,"attempt":attempt,"sensitive_page":True})

@never_cache
def receipt(request,pk):
    order=customer_order(request,pk)
    return render(request,"store/customer_receipt.html",{"order":order,"sensitive_page":True})

class ReturnForm(forms.Form):
    reason=forms.CharField(label="شرح درخواست بررسی مرجوعی",max_length=700,widget=forms.Textarea(attrs={"rows":4}))

@never_cache
@require_http_methods(["GET","POST"])
def return_request(request,pk):
    order=customer_order(request,pk)
    existing=ReturnRequest.objects.filter(order=order).first()
    form=ReturnForm(request.POST if request.method=="POST" else None)
    if request.method=="POST" and not existing and form.is_valid():
        with transaction.atomic():
            locked=Order.objects.select_for_update().get(pk=pk)
            if locked.status!=Order.Status.DELIVERED:
                form.add_error(None,"درخواست بررسی پس از تحویل ثبت می‌شود.")
            else:
                ReturnRequest.objects.get_or_create(order=locked,defaults={"reason":form.cleaned_data["reason"]})
                return redirect("customer_return",pk=pk)
    return render(request,"store/customer_return.html",{"order":order,"existing":existing,"form":form,"can_request":order.status==Order.Status.DELIVERED})

class ReviewForm(forms.Form):
    note=forms.CharField(label="نتیجه بررسی (بدون بازپرداخت خودکار)",max_length=700,widget=forms.Textarea(attrs={"rows":4}))

@manager_only
def returns(request):
    from django.core.paginator import Paginator
    items=ReturnRequest.objects.select_related("order").order_by("-pk")
    return render(request,"store/manager_returns.html",{"page":Paginator(items,30).get_page(request.GET.get("page"))})

@manager_only
@require_http_methods(["GET","POST"])
def review_return(request,pk):
    item=get_object_or_404(ReturnRequest,pk=pk)
    form=ReviewForm(request.POST if request.method=="POST" else None,initial={"note":item.manager_note})
    if request.method=="POST" and form.is_valid():
        ReturnRequest.objects.filter(pk=pk,state=ReturnRequest.State.NEW).update(state=ReturnRequest.State.REVIEWED,manager_note=form.cleaned_data["note"])
        return redirect("manager_returns")
    return render(request,"store/form.html",{"title":"بررسی درخواست مرجوعی","form":form,"submit":"ثبت نتیجه بررسی"})
