from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[("store","0007_checkout_pricing")]
    operations=[
        migrations.CreateModel(name="SandboxPayment",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("amount",models.PositiveBigIntegerField()),
            ("authority",models.CharField(blank=True,max_length=80,null=True,unique=True)),
            ("reference",models.CharField(blank=True,default="",max_length=80)),
            ("state",models.CharField(choices=[("creating","در حال ایجاد"),("ready","آماده آزمون"),("verified","آزمون تأیید شد؛ بدون پرداخت واقعی"),("unknown","نامشخص؛ نیازمند بررسی")],default="creating",max_length=12)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("verified_at",models.DateTimeField(blank=True,null=True)),
            ("order",models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name="sandbox_payment",to="store.order")),
        ]),
        migrations.CreateModel(name="ReturnRequest",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("reason",models.CharField(max_length=700)),
            ("state",models.CharField(choices=[("new","در انتظار بررسی"),("reviewed","بررسی شد؛ بدون تسویه یا مرجوعی خودکار")],default="new",max_length=12)),
            ("manager_note",models.CharField(blank=True,default="",max_length=700)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("order",models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name="return_request",to="store.order")),
        ]),
    ]
