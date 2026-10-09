# AI Chat App (NVIDIA NIM + Telegram + Render)

تطبيق دردشة باستخدام نموذج `meta/muse-glimmer-30b` عبر NVIDIA NIM، مع واجهة ويب وبوت تيليجرام. جاهز للنشر على Render.

## التشغيل محلياً

```bash
pip install -r requirements.txt
cp .env.example .env   # ثم عدّل المفاتيح داخل .env
python app.py
```

## النشر على Render

1. ارفع المشروع على GitHub.
2. Render → **New → Web Service** → اختر الريبو.
3. الإعدادات:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --workers=1 --threads=4 app:app`
     (عامل واحد فقط حتى لا يتضارب استقبال تيليجرام)
4. في **Environment Variables** أضف:
   - `NVIDIA_API_KEY` = مفتاحك من NVIDIA
   - `TELEGRAM_BOT_TOKEN` = توكن بوت تيليجرام
   - `TELEGRAM_ALLOWED_CHAT_IDS` = معرفك على تيليجرام (افتراضي `8952278702`)

> ملاحظة: لا تضع أي مفتاح سري في الكود، استخدم دائماً متغيرات البيئة.
> على الخطة المجانية من Render يتوقف التطبيق بعد 15 دقيقة من عدم الطلبات — استخدم خدمة مثل UptimeRobot لتنبيه المسار `/health` كل 5 دقائق لإبقاء البوت نشيطاً.
