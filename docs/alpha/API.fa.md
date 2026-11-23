# API اراک کالا — نسخه نمونه

`Content-Type: application/json` برای همه درخواست‌های JSON.

| Method | Path | Scope | توضیح |
|---|---|---|---|
| GET | `/api/health` | عمومی | سلامت |
| POST | `/api/auth/register` | عمومی | ایجاد حساب مشتری؛ role همیشه customer |
| POST | `/api/auth/login` | عمومی | دریافت token با عمر ۱۲ ساعت |
| POST | `/api/auth/logout` | کاربر | لغو نشست |
| GET | `/api/me` | کاربر | مشخصات جاری |
| GET | `/api/products` | عمومی | کالاها، پارامتر `search` و `category` |
| GET | `/api/products/{id}` | عمومی | جزئیات |
| POST | `/api/orders` | کاربر | ثبت سفارش آزمایشی؛ محاسبه قیمت سمت سرور |
| GET | `/api/orders` | کاربر | سفارش‌های شخصی |
| GET | `/api/admin/products` | مدیر | همه محصولات حتی غیرفعال |
| POST | `/api/admin/products` | مدیر | ایجاد محصول |
| PATCH | `/api/admin/products/{id}` | مدیر | ویرایش |
| DELETE | `/api/admin/products/{id}` | مدیر | حذف منطقی |
| POST | `/api/admin/images` | مدیر | آپلود Base64، حداکثر ۲ MB |
| GET | `/api/admin/orders` | مدیر | تمام سفارش‌ها و اقلام |
| PATCH | `/api/admin/orders/{id}/status` | مدیر | انتقال معتبر وضعیت |
| GET | `/api/admin/stats` | مدیر | شاخص‌های اولیه |

در مسیر مدیر و مشتری، هدر `Authorization: Bearer <token>` الزامی است.

## مثال ایجاد محصول
```json
{
  "name": "نام محصول واقعی",
  "description": "توضیحات",
  "category": "پوشاک",
  "price": 1290000,
  "stock": 12,
  "images": ["/uploads/<filename>.jpg"]
}
```
نام فایل در نمونه بالا صرفاً قرارداد است؛ فایل باید قبلاً با API تصویر آپلود شده و URL معتبر برگردانده باشد.

## ثبت سفارش آزمایشی
```json
{
  "full_name": "نام گیرنده",
  "phone": "09120000000",
  "address": "نشانی کامل مشتری",
  "items": [{"product_id": 1, "quantity": 2}]
}
```
قیمت‌ها، موجودی و کل سفارش فقط از دیتابیس دریافت می‌شوند، نه از بدنه درخواست کاربر.

وضعیت مجاز: `pending -> processing -> shipped -> delivered`، لغو فقط در `pending` یا `processing` و با بازگشت موجودی.

این API نسخه نمونه است و فاقد تولید فاکتور رسمی، پرداخت، ارسال پیامک یا حفاظت ضد brute-force لازم برای نسخه عمومی است.
