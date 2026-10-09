import os
import re
import urllib.request
import urllib.parse
import telebot
from openai import OpenAI
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

# ==========================================
# 🔑 إعدادات البيئة
# ==========================================

# توكن بوت تيليجرام
TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8902642942:AAHbLDB1iC7qLrEBLeuG-pk3rR_GlUbpgOk"
)

# مفتاح NVIDIA API
NVIDIA_API_KEY = os.getenv(
    "NVIDIA_API_KEY",
    "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"
)

# رابط واجهة NVIDIA NIM
BASE_URL = os.getenv("BASE_URL", "https://integrate.api.nvidia.com/v1")

# قائمة المعرفات المسموح لها بالاستخدام
ALLOWED_CHAT_IDS_STR = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "8952278702")
ALLOWED_CHAT_IDS = set(int(x.strip()) for x in ALLOWED_CHAT_IDS_STR.split(",") if x.strip())

# الموديل الافتراضي
MODEL_NAME = os.getenv("MODEL_NAME", "z-ai/glm-5.3")

# ==========================================
# تهيئة العملاء
# ==========================================

app = FastAPI(title="AI Chat + Telegram Bot with Web Search")

# تهيئة بوت تيليجرام
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode="HTML")

# تهيئة عميل NVIDIA
client = OpenAI(
    base_url=BASE_URL,
    api_key=NVIDIA_API_KEY
)

# دالة البحث المباشر في الويب (بدون مكتبات خارجية)
def search_web(query: str, max_results: int = 3) -> str:
    try:
        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({'q': query})
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode('utf-8', errors='ignore')
            titles = re.findall(r'<a class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
            snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
            
            clean_titles = [re.sub(r'<[^>]+>', '', t).strip() for t in titles]
            clean_snippets = [re.sub(r'<[^>]+>', '', s).strip() for s in snippets]
            
            results = []
            for i in range(min(max_results, len(clean_snippets))):
                title = clean_titles[i] if i < len(clean_titles) else ""
                snippet = clean_snippets[i]
                results.append(f"العنوان: {title}\nالمحتوى: {snippet}")
                
            return "\n\n".join(results)
    except Exception as e:
        print(f"Search error: {e}")
        return ""

# ==========================================
# واجهة الويب
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <body style="font-family: sans-serif; text-align: center; padding: 50px; background: #1a1a2e; color: white;">
            <h1>✅ AI Chat Bot — يعمل بنجاح مع خاصية البحث</h1>
            <p>بوت تيليجرام نشط ومزود بمحرك بحث الويب</p>
        </body>
    </html>
    """

@app.get("/health")
async def health():
    return {"status": "ok", "bot_running": True}

# ==========================================
# أوامر تيليجرام
# ==========================================

@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    if message.chat.id not in ALLOWED_CHAT_IDS:
        bot.reply_to(message, "⛔ غير مصرح لك باستخدام هذا البوت.")
        return
    bot.reply_to(message, "👋 أهلاً! أرسل لي أي سؤال وسأبحث في الويب وأجيبك باستخدام الذكاء الاصطناعي.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.chat.id not in ALLOWED_CHAT_IDS:
        bot.reply_to(message, "⛔ غير مصرح لك باستخدام هذا البوت.")
        return

    try:
        # إرسال إشعار للمستخدم بأن البوت يبحث
        status_msg = bot.reply_to(message, "🔍 جاري البحث في الويب وإعداد الإجابة...")

        # البحث في الويب
        search_data = search_web(message.text)

        # تجهيز الرسائل للذكاء الاصطناعي
        messages = [
            {
                "role": "system",
                "content": "أنت مساعد ذكاء اصطناعي متقدم. استخدم نتائج البحث المرفقة للإجابة عن أسئلة المستخدم بدقة وتنسيق ممتاز باللغة العربية."
            }
        ]

        if search_data:
            messages.append({
                "role": "system",
                "content": f"نتائج البحث الأخيرة من الويب حول سؤال المستخدم:\n{search_data}"
            })

        messages.append({"role": "user", "content": message.text})

        # طلب الإجابة من الذكاء الاصطناعي
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.5,
            max_tokens=1024
        )
        answer = response.choices[0].message.content or "لم أستطع الحصول على إجابة."

        # تعديل الرسالة المؤقتة بنص الإجابة النهائي
        bot.edit_message_text(answer, chat_id=message.chat.id, message_id=status_msg.message_id)

    except Exception as e:
        bot.reply_to(message, f"❌ خطأ في الاتصال بالذكاء الاصطناعي:\n{str(e)}")

# ==========================================
# تشغيل البوت في الخلفية عند بدء التطبيق
# ==========================================

@app.on_event("startup")
async def startup_event():
    import threading
    def run_bot():
        try:
            bot.infinity_polling(timeout=20)
        except Exception as e:
            print(f"Bot polling error: {e}")
    thread = threading.Thread(target=run_bot, daemon=True)
    thread.start()
    print("✅ Telegram Bot started")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
