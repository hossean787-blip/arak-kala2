from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("store", "0004_savedaddress")]
    operations = [
        migrations.CreateModel(
            name="Favorite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="favorites", to="store.customer")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="store.product")),
            ],
            options={"ordering":["-created_at","-pk"]},
        ),
        migrations.AddConstraint(model_name="favorite", constraint=models.UniqueConstraint(fields=["customer","product"],name="unique_customer_favorite")),
    ]
