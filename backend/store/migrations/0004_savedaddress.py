from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("store", "0003_auththrottle")]
    operations = [
        migrations.CreateModel(
            name="SavedAddress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=60, verbose_name="عنوان نشانی")),
                ("recipient", models.CharField(max_length=150, verbose_name="نام گیرنده")),
                ("phone", models.CharField(max_length=11, verbose_name="موبایل")),
                ("address", models.CharField(max_length=700, verbose_name="نشانی کامل")),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="addresses", to="store.customer")),
            ],
            options={"ordering": ["pk"]},
        ),
    ]
