import os
import re
import json
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
# تهيئة العملاء بدون قيود parse_mode
# ==========================================

app = FastAPI(title="AI Chat + Trading Bot")

# إزالة parse_mode لضمان عدم رفض الرسائل من تيليجرام
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = OpenAI(base_url=BASE_URL, api_key=NVIDIA_API_KEY)

chat_histories = {}

# ==========================================
# جلب أسعار الأسواق المباشرة الفورية (Spot)
# ==========================================

def get_live_market_price(query: str) -> str:
    query_lower = query.lower()
    symbol = None
    name = ""

    if any(k in query_lower for k in ["xau", "xauusd", "ذهب", "gold"]):
        symbol, name = "XAUUSD=X", "الذهب الفوري (XAU/USD)"
    elif any(k in query_lower for k in ["فضة", "silver", "xag"]):
        symbol, name = "XAGUSD=X", "الفضة الفورية (XAG/USD)"
    elif any(k in query_lower for k in ["نفط", "oil", "crude", "brent"]):
        symbol, name = "CL=F", "النفط الخام (WTI)"
    elif any(k in query_lower for k in ["btc", "bitcoin", "بيتكوين"]):
        symbol, name = "BTC-USD", "البيتكوين (BTC/USD)"
    elif any(k in query_lower for k in ["eth", "ethereum", "ايثريوم"]):
        symbol, name = "ETH-USD", "الإيثريوم (ETH/USD)"
    elif any(k in query_lower for k in ["eurusd", "يورو"]):
        symbol, name = "EURUSD=X", "اليورو مقابل الدولار (EUR/USD)"
    elif any(k in query_lower for k in ["gbpusd", "باوند"]):
        symbol, name = "GBPUSD=X", "الباوند مقابل الدولار (GBP/USD)"
    elif any(k in query_lower for k in ["usdjpy", "ين"]):
        symbol, name = "USDJPY=X", "الدولار مقابل الين (USD/JPY)"
    elif any(k in query_lower for k in ["us30", "dow", "داو"]):
        symbol, name = "^DJI", "مؤشر الداوجونز (US30)"
    elif any(k in query_lower for k in ["nasdaq", "ناسداك", "us100"]):
        symbol, name = "^IXIC", "مؤشر الناسداك (US100)"

    if not symbol:
        return ""

    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            meta = data['chart']['result'][0]['meta']
            price = meta.get('regularMarketPrice')
            currency = meta.get('currency', 'USD')
            return f"📊 السعر المباشر اللحظي لـ {name}: {price} {currency}"
    except Exception as e:
        print(f"Market price error: {e}")
        return ""

def search_web(query: str, max_results: int = 3) -> str:
    market_price = get_live_market_price(query)
    if market_price:
        return market_price

    try:
        url = "https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode({'q': query})
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode('utf-8', errors='ignore')
            snippets = re.findall(r'<td class="result-snippet"[^>]*>(.*?)</td>', html, re.DOTALL)
            clean_snippets = [re.sub(r'<[^>]+>', '', s).strip() for s in snippets]
            if clean_snippets:
                return "\n\n".join(clean_snippets[:max_results])
    except Exception as e:
        print(f"Search error: {e}")

    return ""

# ==========================================
# واجهة الويب
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def root():
    return "<html><body><h1>✅ AI Chat Bot Active</h1></body></html>"

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
    bot.reply_to(message, "👋 أهلاً بك! أنا جاهز لمساعدتك في التداول والإجابة عن أسئلتك.\nأرسل /clear لمسح الذاكرة.")

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

    status_msg = None
    try:
        status_msg = bot.reply_to(message, "💬 جاري المعالجة والتحليل...")

        history = chat_histories.get(chat_id, [])

        search_query = message.text
        if len(message.text.split()) <= 4 and history:
            last_user_msgs = [m["content"] for m in history if m["role"] == "user"]
            if last_user_msgs:
                search_query = f"{last_user_msgs[-1]} {message.text}"

        search_data = search_web(search_query)

        system_prompt = (
            "أنت مساعد ذكاء اصطناعي ومحلل تداول محترف وصديق شخصي للمستخدم.\n"
            "قدم توصيات صفقات واضحة تشمل (دخول، أهداف، وقف خسارة) بناءً على السعر المباشر المرفق."
        )

        messages_payload = [{"role": "system", "content": system_prompt}]

        if search_data:
            messages_payload.append({
                "role": "system",
                "content": f"بيانات وسعر السوق المباشر الآن:\n{search_data}"
            })

        messages_payload.extend(history[-20:])
        messages_payload.append({"role": "user", "content": message.text})

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages_payload,
            temperature=0.4,
            max_tokens=1024
        )
        answer = response.choices[0].message.content or "لم أستطع الحصول على إجابة."

        history.append({"role": "user", "content": message.text})
        history.append({"role": "assistant", "content": answer})
        chat_histories[chat_id] = history[-30:]

        if status_msg:
            bot.edit_message_text(answer, chat_id=chat_id, message_id=status_msg.message_id)
        else:
            bot.reply_to(message, answer)

    except Exception as e:
        error_text = f"❌ حدث خطأ أثناء المعالجة:\n{str(e)}"
        if status_msg:
            bot.edit_message_text(error_text, chat_id=chat_id, message_id=status_msg.message_id)
        else:
            bot.reply_to(message, error_text)

# ==========================================
# تشغيل البوت
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
