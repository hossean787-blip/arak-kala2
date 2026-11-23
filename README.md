# اراک کالا ۲

فروشگاه فارسی اراک کالا و برنامهٔ اختصاصی اندروید مدیریت محصولات به یک سرور Django و یک پایگاه دادهٔ مشترک وصل‌اند. پنل فروشنده در ویترین عمومی نمایش داده نمی‌شود. پرداخت اینترنتی و ارسال واقعی برای این نسخه تنظیم نشده‌اند.

| مسیر | محتوا |
| --- | --- |
| `backend/` | ویترین اصلی، API، پنل قدیمی، فروش حضوری و مهاجرت‌های داده |
| `android-admin/` | اپ جدید مدیریت با Kotlin و Jetpack Compose |
| `android/` | سورس اپ WebView قبلی برای سازگاری |
| `archives/` | سورس‌ها و خروجی‌های آزمایشی آرشیوی اراک کالا و سپاس |
| `design-references/` | طرح‌های لوگو، ویترین و پیش‌نمایش‌های قبلی |
| [docs/INTEGRATION.fa.md](docs/INTEGRATION.fa.md) | راه‌اندازی، مسیرها و شواهد آزمون ادغام |

## اجرای محلی

Python 3.10 یا بالاتر لازم است. در لینوکس و macOS:

```bash
cd backend
python -m pip install -r requirements.txt
export ARAK_DEVELOPMENT=1
python manage.py migrate
python manage.py setup_manager
python manage.py runserver
```

در Windows از `set ARAK_DEVELOPMENT=1` در CMD یا `$env:ARAK_DEVELOPMENT = "1"` در PowerShell استفاده کنید. ویترین در `http://127.0.0.1:8000/` و پنل قدیمی در مسیر `/manager/login/` باز می‌شوند. حساب مدیر پیش از اولین ورود با دستور `setup_manager` ایجاد می‌شود. برای ارتقای دادهٔ نسخهٔ قبلی از همان فایل SQLite استفاده کنید و قبل از اجرای مهاجرت، از پایگاه داده نسخهٔ پشتیبان بگیرید.

آزمون‌ها با `python manage.py test store` در پوشهٔ `backend` اجرا می‌شوند. راه‌اندازی Android در [android-admin/README.md](android-admin/README.md) آمده است.
