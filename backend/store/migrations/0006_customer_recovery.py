from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("store","0005_favorite")]
    operations=[
        migrations.AddField(model_name="customer",name="recovery_email",field=models.EmailField(max_length=254,unique=True,null=True,blank=True)),
        migrations.AddField(model_name="customer",name="pending_email",field=models.EmailField(max_length=254,blank=True,default="")),
        migrations.AddField(model_name="customer",name="verification_digest",field=models.CharField(max_length=64,blank=True,default="")),
        migrations.AddField(model_name="customer",name="verification_expires",field=models.DateTimeField(null=True,blank=True)),
        migrations.AddField(model_name="customer",name="verification_sent_at",field=models.DateTimeField(null=True,blank=True)),
        migrations.AddField(model_name="customer",name="reset_sent_at",field=models.DateTimeField(null=True,blank=True)),
    ]
