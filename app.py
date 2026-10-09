import os
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
    "nvapi-your-key-here"
)

# رابط واجهة NVIDIA NIM
BASE_URL = os.getenv("BASE_URL", "https://integrate.api.nvidia.com/v1")

# قائمة المعرفات المسموح لها بالاستخدام
ALLOWED_CHAT_IDS_STR = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "8952278702")
ALLOWED_CHAT_IDS = set(int(x.strip()) for x in ALLOWED_CHAT_IDS_STR.split(",") if x.strip())

# الموديل الافتراضي
MODEL_NAME = os.getenv("MODEL_NAME", "meta/muse-glimmer-30b")

# ==========================================
# تهيئة العملاء
# ==========================================

app = FastAPI(title="AI Chat + Telegram Bot")

# تهيئة بوت تيليجرام
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode="HTML")

# تهيئة عميل NVIDIA
client = OpenAI(
    base_url=BASE_URL,
    api_key=NVIDIA_API_KEY
)

# ==========================================
# واجهة الويب
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <body style="font-family: sans-serif; text-align: center; padding: 50px; background: #1a1a2e; color: white;">
            <h1>✅ AI Chat Bot — يعمل بنجاح</h1>
            <p>بوت تيليجرام نشط ويعمل</p>
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
    bot.reply_to(message, "👋 أهلاً! أرسل لي أي سؤال وسأجيب لك باستخدام الذكاء الاصطناعي.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.chat.id not in ALLOWED_CHAT_IDS:
        bot.reply_to(message, "⛔ غير مصرح لك باستخدام هذا البوت.")
        return

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": message.text}],
            temperature=0.7,
            max_tokens=1024
        )
        answer = response.choices[0].message.content or "لم أستطع الحصول على إجابة."
        bot.reply_to(message, answer)
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
