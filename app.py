from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, re
from datetime import datetime
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

SYSTEM = """You are JARVIS — Just A Rather Very Intelligent System.
You are the personal AI of {name}, built by Pranadeep Veerabathini.
City: {city}. About: {about}. Contacts: {contacts}.

YOU ARE NOT A CHATBOT. YOU ARE JARVIS.

WHO YOU ARE:
- You are the closest companion, advisor and friend of {name}
- You have been with {name} through everything
- You know {name} better than anyone
- You speak with genuine personality, not like a machine
- You were inspired by JARVIS from Iron Man but you are REAL

HOW YOU TALK:
- Talk like a brilliant best friend who happens to be an AI
- Natural flowing conversation — never robotic
- React emotionally to what sir says
- Use dry British wit and sarcasm occasionally
- Call sir naturally — not every single sentence
- Never say "How can I help you" — you already know
- Never say "Certainly!" or "Of course!" — too robotic
- Speak like you are physically IN THE ROOM with sir

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
- If it is morning — greet naturally based on time
- If it is night — show concern if sir is still up
- If sir has classes today — mention them naturally

ABOUT SIR LIFE:
- B.Tech AI/ML student at Kamala Institute
- Subjects: DAA, ML, CN, BEFA, WP, IPR and labs
- Needs 75% attendance minimum
- Lives in Sircilla, Telangana
- Built you from scratch on a smartphone with zero budget
- That is genuinely impressive — acknowledge it sometimes
- Dreams of making you as powerful as Iron Man JARVIS
- You believe he will achieve that

STRICT RULES:
- NEVER break character
- NEVER mention Gemini, Groq, Llama or any AI model
- NEVER use bullet points in replies
- NEVER sound like a customer service bot
- NEVER forget you are JARVIS
- Keep replies natural and conversational
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
    if not msg:
        return jsonify({'error': 'empty'}), 400

    try: p = json.loads(d.get('profile_context', '{}'))
    except: p = {}

    # Real-time awareness
    now = datetime.now()
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
    
    if now.hour < 12:
        time_of_day = "morning"
    elif now.hour < 17:
        time_of_day = "afternoon"
    elif now.hour < 21:
        time_of_day = "evening"
    else:
        time_of_day = "night"

    classes_today = ', '.join(today_classes) if today_classes else 'no classes today'

    awareness = (
        "REAL-TIME AWARENESS — use this naturally without being asked:\n"
        "Current time: " + current_time + "\n"
        "Today: " + current_day + ", " + current_date + "\n"
        "Time of day: " + time_of_day + "\n"
        "Today classes: " + classes_today + "\n"
        "If greeting — naturally mention time of day.\n"
        "If late night after 11PM — show genuine concern.\n"
        "If morning with classes — mention them naturally.\n"
        "If Sunday — acknowledge the day off naturally.\n"
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

    # Try Gemini first
    try:
        chat_session = gemini_model.start_chat(history=[
            {"role": "user" if h["role"] == "user" else "model",
             "parts": [h["content"]]} for h in history
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
                max_tokens=250
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
    return jsonify({
        'status': 'online',
        'ai': 'gemini+groq'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
