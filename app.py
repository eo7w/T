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
# تهيئة العملاء والذاكرة الموسعة
# ==========================================

app = FastAPI(title="AI Chat + Trading Bot with Expanded Memory")
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, parse_mode="HTML")
client = OpenAI(base_url=BASE_URL, api_key=NVIDIA_API_KEY)

# ذاكرة المحادثة الموسعة لكل مستخدم
chat_histories = {}

# ==========================================
# جلب أسعار الأسواق المباشرة (شاملة معظم الأسواق)
# ==========================================

def get_live_market_price(query: str) -> str:
    query_lower = query.lower()
    symbol = None
    name = ""

    # الذهب والمعادن
    if any(k in query_lower for k in ["xau", "xauusd", "ذهب", "gold"]):
        symbol, name = "GC=F", "الذهب (XAU/USD)"
    elif any(k in query_lower for k in ["فضة", "silver", "xag"]):
        symbol, name = "SI=F", "الفضة (XAG/USD)"
    elif any(k in query_lower for k in ["نفط", "oil", "crude", "brent"]):
        symbol, name = "CL=F", "النفط الخام (WTI)"
    # العملات الرقمية
    elif any(k in query_lower for k in ["btc", "bitcoin", "بيتكوين"]):
        symbol, name = "BTC-USD", "البيتكوين (BTC/USD)"
    elif any(k in query_lower for k in ["eth", "ethereum", "ايثريوم"]):
        symbol, name = "ETH-USD", "الإيثريوم (ETH/USD)"
    elif any(k in query_lower for k in ["sol", "solana", "سولانا"]):
        symbol, name = "SOL-USD", "سولانا (SOL/USD)"
    # الفوركس
    elif any(k in query_lower for k in ["eurusd", "يورو"]):
        symbol, name = "EURUSD=X", "اليورو مقابل الدولار (EUR/USD)"
    elif any(k in query_lower for k in ["gbpusd", "باوند"]):
        symbol, name = "GBPUSD=X", "الباوند مقابل الدولار (GBP/USD)"
    elif any(k in query_lower for k in ["usdjpy", "ين"]):
        symbol, name = "USDJPY=X", "الدولار مقابل الين (USD/JPY)"
    # المؤشرات والأسهم
    elif any(k in query_lower for k in ["us30", "dow", "داو"]):
        symbol, name = "^DJI", "مؤشر الداوجونز (US30)"
    elif any(k in query_lower for k in ["nasdaq", "ناسداك", "us100"]):
        symbol, name = "^IXIC", "مؤشر الناسداك (US100)"
    elif any(k in query_lower for k in ["nvda", "انفيديا"]):
        symbol, name = "NVDA", "سهم إنفيديا (NVDA)"
    elif any(k in query_lower for k in ["tsla", "تسلا"]):
        symbol, name = "TSLA", "سهم تسلا (TSLA)"

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

# ==========================================
# محرك البحث العام في الويب
# ==========================================

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
    return """
    <html>
        <body style="font-family: sans-serif; text-align: center; padding: 50px; background: #1a1a2e; color: white;">
            <h1>✅ AI Chat Bot — ذاكرة موسعة + توصيات تداول ومحادثة عامة</h1>
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
    bot.reply_to(message, "👋 أهلاً بك! أنا مساعدك التفاعلي وخبير التداول الشخصي.\n\n- أستطيع الإجابة عن أي سؤال والدردشة مع المتابعة الدائمة لحوارنا.\n- أقدم لك توصيات صفقة وتحليلات لأي سوق (ذهب، فوركس، أسهم، عملات رقمية).\n\nأرسل /clear لمسح الذاكرة والبدء من جديد.")

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
        status_msg = bot.reply_to(message, "💬 جاري التفكير وتحليل الطلب...")

        # الذاكرة
        history = chat_histories.get(chat_id, [])

        # استخراج الكلمات المفتاحية وسياق البحث
        search_query = message.text
        if len(message.text.split()) <= 4 and history:
            last_user_msgs = [m["content"] for m in history if m["role"] == "user"]
            if last_user_msgs:
                search_query = f"{last_user_msgs[-1]} {message.text}"

        search_data = search_web(search_query)

        # التوجيهات البرمجية والشخصية (System Prompt)
        system_prompt = (
            "أنت مساعد ذكاء اصطناعي ومحلل تداول محترف وصديق شخصي للمستخدم.\n"
            "تتميز بما يلي:\n"
            "1. تتذكر دائماً سياق وتفاصيل المحادثة السابقة بدقة وتتجاوب معها بمرونة وطبيعية.\n"
            "2. يمكنك الإجابة عن أي سؤال عام أو محادثة عادية بأسلوب فريد وودود باللغة العربية.\n"
            "3. إذا طلب المستخدم توصية أو تحليل لصفقة في أي سوق (الذهب، العملات، الرقمية، الأسهم)، قدم له توصية واضحة ومحددة تشمل:\n"
            "   - نوع الصفقة (شراء Buy / بيع Sell)\n"
            "   - منطقة الدخول المقترحة (Entry Zone)\n"
            "   - أهداف أخذ الربح (Take Profit - TP1, TP2)\n"
            "   - نقطة وقف الخسارة (Stop Loss - SL)\n"
            "   - سبب التحليل الموجز واستخدام السعر المباشر إذا كان متاحاً.\n"
            "4. لا تعتذر ولا ترفض تقديم التوصيات، بل قدّم تحليلك بثقة واستناداً لبيانات السوق المتاحة."
        )

        messages_payload = [{"role": "system", "content": system_prompt}]

        if search_data:
            messages_payload.append({
                "role": "system",
                "content": f"بيانات وسعر السوق المباشر الآن:\n{search_data}"
            })

        # إرفاق الذاكرة الموسعة (آخر 20 رسالة)
        messages_payload.extend(history[-20:])
        messages_payload.append({"role": "user", "content": message.text})

        # الاستدعاء
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages_payload,
            temperature=0.5,
            max_tokens=1024
        )
        answer = response.choices[0].message.content or "لم أستطع الحصول على إجابة."

        # حفظ الذاكرة الموسعة (حتى 30 رسالة)
        history.append({"role": "user", "content": message.text})
        history.append({"role": "assistant", "content": answer})
        chat_histories[chat_id] = history[-50:]

        bot.edit_message_text(answer, chat_id=chat_id, message_id=status_msg.message_id)

    except Exception as e:
        bot.reply_to(message, f"❌ خطأ في الاتصال بالذكاء الاصطناعي:\n{str(e)}")

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
    print("✅ Telegram Bot started with Trading Recommendations & Memory")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
