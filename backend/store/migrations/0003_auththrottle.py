from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("store", "0002_product_images_managertoken")]
    operations = [
        migrations.CreateModel(
            name="AuthThrottle",
            fields=[
                ("key", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("window", models.PositiveBigIntegerField(db_index=True)),
                ("count", models.PositiveIntegerField(default=0)),
            ],
        ),
    ]
