# استقرار و بازیابی اراک کالا

این بسته برای یک فروشگاه تک‌مالک و یک میزبان Linux با Docker Compose v2 است. SQLite فعلاً با یک نمونه برنامه و دو worker/دو thread استفاده می‌شود؛ آزمون فشار واقعی لازم است. برای چند میزبان یا ظرفیت بیشتر، مهاجرت PostgreSQL جداگانه لازم است. هیچ سرور عمومی خریداری یا متصل نشده است.

## راه‌اندازی اولیه (فقط پس از تأیید میزبان و دامنه)
- DNS دامنه واقعی به IP میزبان؛ پورت‌های ۸۰ و ۴۴۳ به Caddy، نه Gunicorn.
- در پوشه deploy، فایل .env را از .env.example بسازید؛ chmod 600، مقدار secret مستقل با python -c 'import secrets; print(secrets.token_urlsafe(64))'، دامنه تأییدشده و بدون DEBUG. هرگز فایل را commit نکنید.
- docker compose build app
- docker compose run --rm app python manage.py migrate --noinput
- docker compose run --rm app python manage.py collectstatic --noinput
- docker compose run --rm app python manage.py setup_manager (فقط اولین راه‌اندازی؛ اجرای مجدد رمز را تغییر می‌دهد)
- docker compose up -d --wait
- HTTPS و /api/ready و /manager/login/ را با گواهی معتبر بررسی کنید. محیط CI فقط localhost با CA داخلی است؛ در محیط واقعی از curl -k استفاده نکنید.
- سرور تنها تصاویر JPEG نرمال‌شده products را ارائه می‌کند. فایل‌های قدیمی غیر استاندارد باید پیش از انتقال با مجوز مالک تبدیل و اعتبارسنجی شوند.

## پشتیبان‌گیری
پیش از هر migration و تغییر مهم، در پنجره نگهداری برنامه را متوقف کنید تا دیتابیس و تصاویر همگام باشند. پوشه پشتیبان خصوصی خارج Git با مالک UID 10001 بسازید، مسیر میزبان را به /backups متصل کنید. مثال:
```sh
docker compose stop proxy app
docker compose run --rm --no-deps -v /secure/arak-backups:/backups app python ops/backup.py create --db /data/store.sqlite3 --media /media --output /backups/arak-2026-01-01.tar.gz
docker compose up -d --wait
```
نسخه پشتیبان حاوی اطلاعات خصوصی مشتری است؛ آن را رمزگذاری و خارج میزبان نگهداری کنید. فایل backup.py حذف یا بازنویسی پشتیبان موجود ندارد. برای آزمون بازیابی، با همان mount دستور restore --archive /backups/... --destination /backups/restore-test را اجرا کنید. خروجی جدید با checksum و SQLite integrity بررسی می‌شود؛ جایگزینی داده زنده فقط پس از پشتیبان جدید، توقف سرویس و تأیید مالک. CI بازیابی داده آزمایشی و رد فایل مسیر نامعتبر را بررسی می‌کند.

## انتشار
- دامنه/HTTPS، SMTP واقعی، پذیرنده پرداخت، تعرفه ارسال، سیاست‌های تجاری، محصولات واقعی و اطلاعات تماس باید تعیین و آزموده شوند.
- ساخت APK: debug پیش‌فرض شبیه‌ساز است؛ برای گوشی -PARAK_DEBUG_API_BASE_URL=https://your-domain/api. release نیازمند -PARAK_API_BASE_URL=https://your-domain/api و امضای خصوصی خارج Git است.
- آزمون واقعی گوشی، سناریوهای پرداخت ناموفق/تکراری، برگشت وجه، امنیت، بار و بازیابی خارج میزبان پیش‌شرط انتشار است.
- دستور docker compose down -v روی میزبان واقعی ممنوع؛ حجم داده را حذف می‌کند. CI فقط کانتینر و volume آزمایشی را پاک می‌کند.
