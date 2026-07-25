# سرویس تبدیل صوت به متن فارسی Whisper Large

این مخزن نسخهٔ قابل‌توسعه و Docker-based سرویس تبدیل فایل صوتی به متن است. پروژه شامل رابط آپلود فارسی، Swagger، API سازگار با OpenAI و موتور GPU مبتنی بر Whisper Large است.

## اجرای سریع

پیش‌نیازها: Docker، Docker Compose، کارت NVIDIA، درایور سازگار و NVIDIA Container Toolkit.

```bash
cp .env.example .env
```

مقدار `ENGINE_API_KEY` را در فایل `.env` تغییر دهید و سپس اجرا کنید:

```bash
docker compose up -d --build
```

اگر سرور از NVIDIA CDI استفاده می‌کند:

```bash
docker compose -f compose.yaml -f compose.cdi.yaml up -d --build
```

## آدرس‌های پیش‌فرض

| بخش | آدرس |
|---|---|
| رابط آپلود | <http://localhost:8101/> |
| Swagger | <http://localhost:8101/docs> |
| ReDoc | <http://localhost:8101/redoc> |
| سلامت سرویس | <http://localhost:8101/health> |
| API | `POST http://localhost:8101/v1/audio/transcriptions` |

در Swagger مسیر استاندارد `POST /v1/audio/transcriptions` را باز کنید، مقدار `model` را روی `whisper-1` قرار دهید، فایل را انتخاب و **Execute** را فشار دهید.

## نمونه درخواست

```bash
curl -F "file=@sample.wav" \
  -F "model=whisper-1" \
  -F "language=fa" \
  -F "response_format=json" \
  http://localhost:8101/v1/audio/transcriptions
```

## پایداری

- موتور و API دارای `restart: always` هستند.
- هر دو کانتینر healthcheck دارند.
- مدل دانلودشده در volume دائمی نگهداری می‌شود.
- تعداد درخواست هم‌زمان GPU محدود است تا حافظه پایدار بماند.
- لاگ‌ها دارای چرخش و سقف حجم هستند.
- موتور روی شبکهٔ داخلی Docker است و مستقیماً publish نمی‌شود.

## مستندات تکمیلی

- [معماری](docs/architecture.md)
- [API](docs/api.md)
- [استقرار](docs/deployment.md)
- [نگهداری و مانیتورینگ](docs/operations.md)
- [توسعه](docs/development.md)

## نکتهٔ امنیتی

API عمومی در نسخهٔ پایه احراز هویت کاربر ندارد. برای انتشار روی اینترنت، آن را پشت reverse proxy دارای TLS و احراز هویت قرار دهید. کلید داخلی موتور را نیز در `.env` با مقدار قوی جایگزین کنید.
