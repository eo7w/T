import os
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI

app = Flask(__name__)

# اقرأ المفتاح والـ base_url من متغيرات البيئة (Render dashboard)
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
BASE_URL = os.environ.get("BASE_URL", "https://integrate.api.nvidia.com/v1")
MODEL = os.environ.get("MODEL", "meta/muse-glimmer-30b")

client = OpenAI(base_url=BASE_URL, api_key=NVIDIA_API_KEY)

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


@app.route("/api/chat", methods=["POST"])
def chat():
    if not NVIDIA_API_KEY:
        return jsonify({"error": "NVIDIA_API_KEY غير مُعد. أضفه في إعدادات Render."}), 500

    data = request.get_json(force=True)
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "الرسالة فارغة"}), 400

    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": message}],
            temperature=1,
            top_p=0.95,
            max_tokens=8192,
            stream=False,
        )
        reply = completion.choices[0].message.content
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Render يستخدم متغير PORT تلقائياً
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
