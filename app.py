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

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8902642942:AAHbLDB1iC7qLrEBLeuG-pk3rR_GlUbpgOk"
)

NVIDIA_API_KEY = os.getenv(
    "NVIDIA_API_KEY",
    "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"
)

BASE_URL = os.getenv("BASE_URL", "https://integrate.api.nvidia.com/v1")

ALLOWED_CHAT_IDS_STR = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "8952278702")
ALLOWED_CHAT_IDS = set(int(x.strip()) for x in ALLOWED_CHAT_IDS_STR.split(",") if x.strip())

MODEL_NAME = os.getenv("MODEL_NAME", "z-ai/glm-5.3")

# ==========================================
# تهيئة العملاء والذاكرة
# ==========================================

app = FastAPI(title="AI Chat + Telegram Bot with Memory & Search")
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode="HTML")
client = OpenAI(base_url=BASE_URL, api_key=NVIDIA_API_KEY)

# قاموس لحفظ ذاكرة المحادثة لكل مستخدم
chat_histories = {}

# دالة البحث في الويب
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
            <h1>✅ AI Chat Bot — يعمل مع الذاكرة والبحث</h1>
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
    bot.reply_to(message, "👋 أهلاً بك! أنا مزود بذاكرة تترابط مع محادثاتنا ومحرك بحث للويب.\nأرسل /clear لمسح الذاكرة وتغيير الموضوع.")

@bot.message_handler(commands=["clear", "reset"])
def clear_memory(message):
    chat_id = message.chat.id
    if chat_id in chat_histories:
        chat_histories[chat_id] = []
    bot.reply_to(message, "🧹 تم مسح الذاكرة وبدء محادثة جديدة!")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    if chat_id not in ALLOWED_CHAT_IDS:
        bot.reply_to(message, "⛔ غير مصرح لك باستخدام هذا البوت.")
        return

    try:
        status_msg = bot.reply_to(message, "🔍 جاري التفكير والبحث...")

        # الحصول على ذاكرة المستخدم الحالية
        history = chat_histories.get(chat_id, [])

        # تحديد جملة البحث: إذا كانت الرسالة قصيرة، يتم إرفاق آخر موضوع تحدث عنه
        search_query = message.text
        if len(message.text.split()) <= 5 and history:
            last_user_msgs = [m["content"] for m in history if m["role"] == "user"]
            if last_user_msgs:
                search_query = f"{last_user_msgs[-1]} {message.text}"

        # إجراء البحث في الويب
        search_data = search_web(search_query)

        # تجهيز الرسائل للنموذج (مع إضافة الذاكرة)
        messages_payload = [
            {
                "role": "system",
                "content": "أنت مساعد ذكاء اصطناعي متقدم. تتذكر سياق المحادثة المرفقة وتستخدم نتائج البحث لإجابة أسئلة المستخدم بدقة وتنسيق ممتاز باللغة العربية."
            }
        ]

        if search_data:
            messages_payload.append({
                "role": "system",
                "content": f"نتائج البحث الحالية من الويب (استخدمها لإجابة المستخدم عن الأسعار والأخبار):\n{search_data}"
            })

        # إضافة السجل السابق للمحادثة (آخر 8 رسائل)
        messages_payload.extend(history[-8:])

        # إضافة الرسالة الجديدة
        messages_payload.append({"role": "user", "content": message.text})

        # استدعاء الذكاء الاصطناعي
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages_payload,
            temperature=0.5,
            max_tokens=1024
        )
        answer = response.choices[0].message.content or "لم أستطع الحصول على إجابة."

        # تحديث الذاكرة للمستخدم
        history.append({"role": "user", "content": message.text})
        history.append({"role": "assistant", "content": answer})
        chat_histories[chat_id] = history[-10:] # الاحتفاظ بآخر 10 رسائل فقط

        # تعديل الرسالة بالإجابة
        bot.edit_message_text(answer, chat_id=chat_id, message_id=status_msg.message_id)

    except Exception as e:
        bot.reply_to(message, f"❌ خطأ في الاتصال بالذكاء الاصطناعي:\n{str(e)}")

# ==========================================
# تشغيل البوت في الخلفية
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
    print("✅ Telegram Bot started with Memory")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
