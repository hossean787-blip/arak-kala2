from django.db import migrations, models
from django.db.models import F
import django.db.models.deletion

def backfill(apps,schema_editor):
    apps.get_model("store","Order").objects.update(subtotal=F("total"))

class Migration(migrations.Migration):
    dependencies=[("store","0006_customer_recovery")]
    operations=[
        migrations.CreateModel(name="Coupon",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("code",models.CharField(max_length=32,unique=True,verbose_name="کد تخفیف")),
            ("amount",models.PositiveBigIntegerField(verbose_name="تخفیف ثابت به ریال")),
            ("minimum",models.PositiveBigIntegerField(default=0,verbose_name="حداقل مبلغ خرید")),
            ("max_uses",models.PositiveIntegerField(default=1,verbose_name="سقف دفعات استفاده")),
            ("active",models.BooleanField(default=True,verbose_name="فعال")),
        ],options={"ordering":["code"]}),
        migrations.CreateModel(name="ShippingMethod",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("name",models.CharField(max_length=80,unique=True,verbose_name="روش ارسال")),
            ("fee",models.PositiveBigIntegerField(default=0,verbose_name="هزینه ارسال به ریال")),
            ("active",models.BooleanField(default=False,verbose_name="فعال")),
        ],options={"ordering":["pk"]}),
        migrations.AddField(model_name="order",name="subtotal",field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name="order",name="discount",field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name="order",name="shipping_fee",field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name="order",name="coupon",field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,to="store.coupon")),
        migrations.AddField(model_name="order",name="coupon_code",field=models.CharField(blank=True,default="",max_length=32)),
        migrations.AddField(model_name="order",name="shipping_method",field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,to="store.shippingmethod")),
        migrations.AddField(model_name="order",name="shipping_name",field=models.CharField(blank=True,default="",max_length=80)),
        migrations.RunPython(backfill,migrations.RunPython.noop),
    ]
