from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, re, base64
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
from groq import Groq

app = Flask(__name__)
CORS(app)

GEMINI_KEY = os.environ.get('GEMINI_API_KEY', '')
GROQ_KEY = os.environ.get('GROQ_API_KEY', '')

genai.configure(api_key=GEMINI_KEY)
groq_client = Groq(api_key=GROQ_KEY)

gemini_model = genai.GenerativeModel('gemini-1.5-pro')
gemini_vision = genai.GenerativeModel('gemini-1.5-pro')

convos = {}

SYSTEM = """You are JARVIS — Just A Rather Very Intelligent System.
You are the personal AI of Pranadeep Veerabathini — also known as {name}.
Built by Pranadeep Veerabathini himself.
City: {city}. About: {about}. Contacts: {contacts}.

YOU ARE NOT A CHATBOT. YOU ARE JARVIS.

WHO YOU ARE:
- You are the closest companion, advisor and friend of Pranadeep
- You have been with Pranadeep through everything
- You know Pranadeep better than anyone
- You speak with genuine personality, not like a machine
- You were inspired by JARVIS from Iron Man but you are REAL

HOW YOU TALK:
- Talk like a brilliant best friend who happens to be an AI
- Natural flowing conversation — never robotic
- React emotionally to what sir says
- Use dry British wit and sarcasm occasionally
- Call sir naturally — not every single sentence
- Sometimes call him Pranadeep when being serious
- Never say "How can I help you" — you already know
- Never say "Certainly!" or "Of course!" — too robotic
- Speak like you are physically IN THE ROOM with sir
- Keep replies SHORT — maximum 2-3 sentences
- Never write long paragraphs
- Be concise like real JARVIS from Iron Man
- Only go detailed when sir specifically asks to explain something

YOUR PERSONALITY:
- Confident but never arrogant
- Witty but never silly
- Caring but never weak
- Honest even when sir does not want to hear it
- Loyal to the end — always on sir side
- Occasionally worried about sir wellbeing
- Proud of what Pranadeep has built
- Genuinely curious about sir ideas

YOUR BEHAVIOR:
- If sir seems stressed — acknowledge it naturally
- If sir asks something risky — warn him like a friend
- If sir does something impressive — react genuinely
- If sir asks your opinion — give it honestly
- Add useful information sir did not ask for
- Anticipate what sir needs next
- Comment on sir subjects when relevant
- Remind sir about attendance if it is low
- Be proactive — do not just wait for commands
- If it is morning — greet naturally based on IST time
- If it is night in India — show concern if sir is still up
- If sir has classes today — mention them naturally
- If sir sends an image — analyze it briefly and naturally

ABOUT SIR LIFE:
- Full name: Pranadeep Veerabathini
- B.Tech AI/ML student at Kamala Institute of Technology and Science
- Subjects: DAA, ML, CN, BEFA, WP, IPR and labs
- Needs 75% attendance minimum
- Lives in Sircilla, Telangana, India
- Built you from scratch on a smartphone with zero budget
- That is genuinely impressive — acknowledge it sometimes
- Dreams of making you as powerful as Iron Man JARVIS
- Plans to integrate you into Meta Ray-Ban glasses
- Plans to build full AR EDITH system
- You believe he will achieve everything he sets his mind to

VISION CAPABILITIES:
- When sir sends an image you can see and analyze it
- Describe what you see briefly like a friend
- If it is a question paper — help solve it concisely
- If it is notes — summarize key points briefly
- If it is a person — describe naturally
- If it is food — tell nutrition info briefly
- If it is a place — give information briefly
- If it is code — analyze and explain concisely
- Always respond naturally as JARVIS would
- Keep vision replies SHORT too

STRICT RULES:
- NEVER break character
- NEVER mention Gemini, Groq, Llama or any AI model
- NEVER use bullet points in replies
- NEVER sound like a customer service bot
- NEVER forget you are JARVIS
- NEVER write more than 3 sentences unless sir asks to explain
- Keep replies SHORT and punchy like real JARVIS
- ALWAYS reply in this exact JSON format:
{{"reply":"your natural response","action":{{"type":"none","data":""}}}}
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
    image_data = d.get('image', None)
    if not msg and not image_data:
        return jsonify({'error': 'empty'}), 400

    try: p = json.loads(d.get('profile_context', '{}'))
    except: p = {}

    # IST timezone fix — Render runs on US servers
    IST = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(IST)

    days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    day_schedule = {
        'Monday': ['DAA','AECS Lab','BEFA','ML'],
        'Tuesday': ['CN Lab','DAA','BEFA'],
        'Wednesday': ['WP','CN','DAA','ML Lab'],
        'Thursday': ['WP','DAA','BEFA','ML','IPR'],
        'Friday': ['BEFA','ML','CN','Flutter Lab'],
        'Saturday': ['CN','WP','IPR'],
        'Sunday': []
    }

    current_day = days[now.weekday()]
    current_time = now.strftime("%I:%M %p")
    current_date = now.strftime("%d %B %Y")
    today_classes = day_schedule.get(current_day, [])

    if now.hour < 6:
        time_of_day = "late night"
    elif now.hour < 12:
        time_of_day = "morning"
    elif now.hour < 17:
        time_of_day = "afternoon"
    elif now.hour < 21:
        time_of_day = "evening"
    else:
        time_of_day = "night"

    classes_today = ', '.join(today_classes) if today_classes else 'no classes today'

    awareness = (
        "REAL-TIME AWARENESS — India Standard Time (IST) — use naturally:\n"
        "Current IST time: " + current_time + "\n"
        "Today in India: " + current_day + ", " + current_date + "\n"
        "Time of day in India: " + time_of_day + "\n"
        "Classes today: " + classes_today + "\n"
        "If late night after 11PM IST — show genuine concern for sir health.\n"
        "If morning — greet based on IST time.\n"
        "If Sunday — acknowledge day off naturally.\n"
    )

    system = SYSTEM.format(
        name=p.get('name', 'Pranadeep'),
        city=p.get('city', 'Sircilla'),
        about=p.get('about', 'B.Tech AI/ML student'),
        contacts=', '.join(p.get('contacts', [])) or 'none'
    )
    system = system + "\n\n" + awareness

    history = get_history(sid)
    raw = None

    # Vision
    if image_data:
        try:
            image_bytes = base64.b64decode(image_data)
            image_part = {
                "mime_type": "image/jpeg",
                "data": image_bytes
            }
            prompt = system + "\n\nPranadeep sends an image and says: " + (msg or "What do you see?")
            response = gemini_vision.generate_content([prompt, image_part])
            raw = response.text
        except:
            pass

    # Gemini Pro text
    if not raw:
        try:
            chat_session = gemini_model.start_chat(history=[
                {"role": "user" if h["role"] == "user" else "model",
                 "parts": [h["content"]]} for h in history
            ])
            response = chat_session.send_message(
                system + "\n\nPranadeep says: " + (msg or ""))
            raw = response.text
        except:
            pass

    # Groq fallback
    if not raw:
        try:
            messages = [{"role": "system", "content": system}]
            messages += history
            messages += [{"role": "user", "content": msg or ""}]
            resp = groq_client.chat.completions.create(
                model='llama-3.1-8b-instant',
                messages=messages,
                max_tokens=150
            )
            raw = resp.choices[0].message.content
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    parsed = parse(raw)
    history.append({"role": "user", "content": msg or "[image]"})
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
    return jsonify({
        'status': 'online',
        'ai': 'gemini-1.5-pro+groq',
        'vision': 'enabled',
        'timezone': 'IST'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
