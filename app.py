from openai import OpenAI
import telebot
from flask import Flask

NVIDIA_API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL_NAME = "meta/muse-glimmer-30b"

TELEGRAM_BOT_TOKEN = "8902642942:AAHbLDB1iC7qLrEBLeuG-pk3rR_GlUbpgOk"
ALLOWED_CHAT_ID = 8952278702

client = OpenAI(
    base_url=BASE_URL,
    api_key=NVIDIA_API_KEY
)

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
app = Flask(__name__)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.chat.id != ALLOWED_CHAT_ID:
        bot.reply_to(message, "عذراً، هذا البوت خاص.")
        return
    
    user_text = message.text
    bot.send_message(message.chat.id, "جاري التفكير... 🤔")
    
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": user_text}],
            temperature=1,
            top_p=0.95,
            max_tokens=1024,
            stream=False
        )
        response = completion.choices[0].message.content
        bot.reply_to(message, response)
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}")

@app.route('/')
def health():
    return "✅ البوت يعمل!"

if __name__ == "__main__":
    import threading
    def run_bot():
        bot.infinity_polling()
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
