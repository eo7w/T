# AI Chat App (NVIDIA NIM + Render)

تطبيق دردشة بسيط باستخدام نموذج `meta/muse-glimmer-30b` عبر NVIDIA NIM API، جاهز للنشر على Render.

## التشغيل محلياً

```bash
pip install -r requirements.txt
cp .env.example .env   # ثم عدّل المفتاح داخل .env
python app.py
```

## النشر على Render

1. ارفع المشروع على GitHub.
2. في Render → **New → Web Service** → اختر الريبو.
3. الإعدادات:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
4. في **Environment Variables** أضف:
   - `NVIDIA_API_KEY` = مفتاحك من NVIDIA
   - `MODEL` = `meta/muse-glimmer-30b` (اختياري)

> ملاحظة: لا تضع المفتاح السري في الكود أبداً، استخدم دائماً متغيرات البيئة.
