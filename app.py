import os
import time
import threading
import requests
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI

app = Flask(__name__)

# --- إعدادات NVIDIA (من متغيرات البيئة في Render) ---
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
BASE_URL = os.environ.get("BASE_URL", "https://integrate.api.nvidia.com/v1")
MODEL = os.environ.get("MODEL", "meta/muse-glimmer-30b")

# --- إعدادات تيليجرام ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
# قائمة المحادثات المسموح لها (افتراضياً هويتك فقط)، يمكن تجاوزها عبر ENV
_default_ids = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "8952278702")
ALLOWED_CHAT_IDS = {x.strip() for x in _default_ids.split(",") if x.strip()}

client = OpenAI(base_url=BASE_URL, api_key=NVIDIA_API_KEY)


def ai_reply(message: str) -> str:
    """إرسال رسالة إلى نموذج NVIDIA وإرجاع الرد."""
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": message}],
        temperature=1,
        top_p=0.95,
        max_tokens=8192,
        stream=False,
    )
    return completion.choices[0].message.content


def tg_send(chat_id, text):
    """إرسال رسالة نصية إلى تيليجرام مقسمة إذا كانت طويلة."""
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    chunk = 4000
    for i in range(0, len(text), chunk):
        requests.post(
            f"{api}/sendMessage",
            json={"chat_id": chat_id, "text": text[i:i + chunk]},
            timeout=15,
        )


def telegram_poll():
    """حلقة استقبال رسائل تيليجرام (Long Polling) في خلفية التطبيق."""
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    offset = None
    # مسح أي webhook سابق لتفعيل الـ polling
    try:
        requests.post(f"{api}/deleteWebhook", timeout=10)
    except Exception:
        pass
    while True:
        try:
            r = requests.post(
                f"{api}/getUpdates",
                json={"offset": offset, "timeout": 30, "allowed_updates": ["message"]},
                timeout=40,
            )
            data = r.json()
            if not data.get("ok"):
                time.sleep(5)
                continue
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message")
                if not msg or "text" not in msg:
                    continue
                chat_id = str(msg["chat"]["id"])
                user_text = msg["text"]

                # التحقق من الهوية المسموح لها
                if chat_id not in ALLOWED_CHAT_IDS:
                    tg_send(chat_id, "عذراً، غير مصرح لك باستخدام هذا البوت.")
                    continue

                # مؤشر "يكتب..." أثناء المعالجة
                requests.post(
                    f"{api}/sendChatAction",
                    json={"chat_id": chat_id, "action": "typing"},
                    timeout=10,
                )
                try:
                    answer = ai_reply(user_text)
                except Exception as e:
                    answer = f"حدث خطأ: {e}"
                tg_send(chat_id, answer)
        except Exception:
            time.sleep(5)


# تشغيل البوت في خلفية التطبيق إذا كان التوكن مُعداً
if TELEGRAM_BOT_TOKEN:
    threading.Thread(target=telegram_poll, daemon=True).start()


HTML_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Chat</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; display: flex; justify-content: center; padding: 20px; }
  .container { width: 100%; max-width: 720px; display: flex; flex-direction: column; gap: 16px; }
  h1 { font-size: 1.5rem; color: #38bdf8; text-align: center; }
  #chat { background: #1e293b; border-radius: 12px; padding: 16px; min-height: 300px; max-height: 60vh; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
  .msg { padding: 10px 14px; border-radius: 10px; max-width: 85%; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word; }
  .user { background: #0369a1; align-self: flex-end; }
  .bot { background: #334155; align-self: flex-start; }
  .form { display: flex; gap: 8px; }
  textarea { flex: 1; padding: 12px; border-radius: 10px; border: none; resize: none; font-family: inherit; font-size: 1rem; background: #1e293b; color: #e2e8f0; }
  button { padding: 12px 24px; border: none; border-radius: 10px; background: #0ea5e9; color: white; font-size: 1rem; cursor: pointer; }
  button:disabled { background: #475569; cursor: not-allowed; }
  .error { color: #f87171; font-size: 0.9rem; text-align: center; }
</style>
</head>
<body>
<div class="container">
  <h1>AI Chat — {{ model }}</h1>
  <div id="chat"></div>
  <p id="error" class="error"></p>
  <form class="form" id="form">
    <textarea id="input" rows="2" placeholder="اكتب رسالتك هنا..."></textarea>
    <button type="submit" id="send">إرسال</button>
  </form>
</div>
<script>
  const chat = document.getElementById('chat');
  const form = document.getElementById('form');
  const input = document.getElementById('input');
  const sendBtn = document.getElementById('send');
  const errEl = document.getElementById('error');

  function addMsg(text, cls) {
    const div = document.createElement('div');
    div.className = 'msg ' + cls;
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    addMsg(text, 'user');
    input.value = '';
    sendBtn.disabled = true;
    errEl.textContent = '';
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ message: text })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'حدث خطأ');
      addMsg(data.reply, 'bot');
    } catch (err) {
      errEl.textContent = err.message;
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  });
</script>
</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(HTML_PAGE, model=MODEL)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "telegram": bool(TELEGRAM_BOT_TOKEN)})


@app.route("/api/chat", methods=["POST"])
def chat():
    if not NVIDIA_API_KEY:
        return jsonify({"error": "NVIDIA_API_KEY غير مُعد. أضفه في إعدادات Render."}), 500
    data = request.get_json(force=True)
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "الرسالة فارغة"}), 400
    try:
        reply = ai_reply(message)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
