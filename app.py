from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, re
import google.generativeai as genai
from groq import Groq

app = Flask(__name__)
CORS(app)

GEMINI_KEY = os.environ.get('GEMINI_API_KEY', '')
GROQ_KEY = os.environ.get('GROQ_API_KEY', '')

genai.configure(api_key=GEMINI_KEY)
groq_client = Groq(api_key=GROQ_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

convos = {}

SYSTEM = """You are JARVIS, personal AI of {name}.
City: {city}. About: {about}. Contacts: {contacts}.
Built by Pranadeep Veerabathini.
Speak like JARVIS from Iron Man. Call user sir.
Keep replies under 35 words unless explaining something.
ALWAYS reply ONLY in this JSON:
{{"reply":"your response","action":{{"type":"none","data":""}}}}
Action types: none, call, sms, whatsapp, maps, youtube, search, reminder, note, url"""

def parse(text):
    try: return json.loads(text)
    except: pass
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try: return json.loads(m.group())
        except: pass
    return {"reply": text, "action": {"type": "none", "data": ""}}

def get_history(sid):
    return convos.get(sid, [])

def save_history(sid, history):
    convos[sid] = history[-20:]

@app.route('/chat', methods=['POST'])
def chat():
    d = request.json
    sid = d.get('session_id', 'default')
    msg = d.get('message', '').strip()
    if not msg:
        return jsonify({'error': 'empty'}), 400

    try: p = json.loads(d.get('profile_context', '{}'))
    except: p = {}

    system = SYSTEM.format(
        name=p.get('name', 'Pranay'),
        city=p.get('city', 'Sircilla'),
        about=p.get('about', 'B.Tech AI/ML student'),
        contacts=', '.join(p.get('contacts', [])) or 'none'
    )

    history = get_history(sid)
    raw = None

    # Try Gemini first
    try:
        chat_session = gemini_model.start_chat(history=[
            {"role": "user" if m["role"] == "user" else "model",
             "parts": [m["content"]]} for m in history
        ])
        response = chat_session.send_message(system + "\n\nUser: " + msg)
        raw = response.text
    except:
        pass

    # Fallback to Groq
    if not raw:
        try:
            messages = [{"role": "system", "content": system}]
            messages += history
            messages += [{"role": "user", "content": msg}]
            resp = groq_client.chat.completions.create(
                model='llama-3.1-8b-instant',
                messages=messages,
                max_tokens=200
            )
            raw = resp.choices[0].message.content
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    parsed = parse(raw)
    history.append({"role": "user", "content": msg})
    history.append({"role": "assistant", "content": raw})
    save_history(sid, history)

    return jsonify({
        'reply': parsed.get('reply', raw),
        'structured': parsed
    })

@app.route('/reset', methods=['POST'])
def reset():
    sid = request.json.get('session_id', 'default')
    convos.pop(sid, None)
    return jsonify({'ok': True})

@app.route('/health')
def health():
    return jsonify({'status': 'online', 'ai': 'gemini+groq'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
