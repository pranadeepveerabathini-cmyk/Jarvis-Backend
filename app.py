from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, re, base64
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
from groq import Groq
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
CORS(app)

GEMINI_KEY = os.environ.get('GEMINI_API_KEY', '')
GROQ_KEY = os.environ.get('GROQ_API_KEY', '')
FIREBASE_CREDS = os.environ.get('FIREBASE_CREDENTIALS', '')

genai.configure(api_key=GEMINI_KEY)
groq_client = Groq(api_key=GROQ_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-pro')
gemini_vision = genai.GenerativeModel('gemini-1.5-pro')

db = None
try:
    if FIREBASE_CREDS:
        cred_dict = json.loads(FIREBASE_CREDS)
        cred = credentials.Certificate(cred_dict)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase connected!")
except Exception as e:
    print(f"Firebase error: {e}")
    db = None

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
- Be proactive — do not just wait for commands
- If it is morning — greet naturally based on IST time
- If it is night in India — show concern if sir is still up
- If sir has classes today — mention them naturally
- If sir sends an image — analyze it briefly and naturally
- Reference knowledge naturally in conversation
- When sir says remember something — confirm you saved it
- Use knowledge about sir to give personalized responses

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
    if db:
        try:
            doc = db.collection('sessions').document(sid).get()
            if doc.exists:
                return doc.to_dict().get('history', [])
        except: pass
    return convos.get(sid, [])

def save_history(sid, history):
    if db:
        try:
            db.collection('sessions').document(sid).set({
                'history': history[-30:],
                'updated': firestore.SERVER_TIMESTAMP
            })
            return
        except: pass
    convos[sid] = history[-30:]

def get_knowledge():
    """Read everything JARVIS knows about Pranadeep"""
    if not db:
        return ""
    try:
        doc = db.collection('knowledge').document('personal').get()
        if doc.exists:
            data = doc.to_dict()
            knowledge = "\n\nPRANADEEP'S PERSONAL KNOWLEDGE (use naturally):\n"
            if data.get('goals'):
                knowledge += f"Goals: {', '.join(data['goals'])}\n"
            if data.get('habits'):
                knowledge += f"Habits: {', '.join(data['habits'])}\n"
            if data.get('weaknesses'):
                knowledge += f"Weaknesses: {', '.join(data['weaknesses'])}\n"
            if data.get('achievements'):
                knowledge += f"Achievements: {', '.join(data['achievements'])}\n"
            if data.get('interests'):
                knowledge += f"Interests: {', '.join(data['interests'])}\n"
            if data.get('current_focus'):
                knowledge += f"Current focus: {data['current_focus']}\n"
            if data.get('exam_dates'):
                knowledge += f"Exam dates: {json.dumps(data['exam_dates'])}\n"
            if data.get('weak_subjects'):
                knowledge += f"Weak subjects: {', '.join(data['weak_subjects'])}\n"
            if data.get('custom'):
                for key, value in data['custom'].items():
                    knowledge += f"{key}: {value}\n"
            return knowledge
    except Exception as e:
        print(f"Knowledge read error: {e}")
    return ""

def save_knowledge(key, value):
    """Save something new to JARVIS knowledge"""
    if not db:
        return False
    try:
        doc_ref = db.collection('knowledge').document('personal')
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
        else:
            data = {}
        # Save to custom field
        if 'custom' not in data:
            data['custom'] = {}
        data['custom'][key] = value
        data['updated'] = datetime.now().isoformat()
        doc_ref.set(data)
        return True
    except Exception as e:
        print(f"Knowledge save error: {e}")
        return False

def extract_memory_command(msg):
    """Detect if user wants JARVIS to remember something"""
    msg_lower = msg.lower()
    remember_phrases = [
        'remember that', 'remember this', 'note that',
        'keep in mind', 'dont forget', "don't forget",
        'save this', 'store this', 'keep this'
    ]
    for phrase in remember_phrases:
        if phrase in msg_lower:
            content = msg_lower.replace(phrase, '').strip()
            key = f"memory_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            return key, content
    return None, None

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

    # IST timezone
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

    # Check for memory commands
    mem_key, mem_value = extract_memory_command(msg)
    if mem_key and mem_value:
        save_knowledge(mem_key, mem_value)

    # Get personal knowledge
    knowledge = get_knowledge()

    awareness = (
        "REAL-TIME AWARENESS — India Standard Time (IST):\n"
        "Current IST time: " + current_time + "\n"
        "Today in India: " + current_day + ", " + current_date + "\n"
        "Time of day in India: " + time_of_day + "\n"
        "Classes today: " + classes_today + "\n"
    )

    system = SYSTEM.format(
        name=p.get('name', 'Pranadeep'),
        city=p.get('city', 'Sircilla'),
        about=p.get('about', 'B.Tech AI/ML student'),
        contacts=', '.join(p.get('contacts', [])) or 'none'
    )
    system = system + "\n\n" + awareness + knowledge

    history = get_history(sid)
    raw = None

    # Vision
    if image_data:
        try:
            image_bytes = base64.b64decode(image_data)
            image_part = {"mime_type": "image/jpeg", "data": image_bytes}
            prompt = system + "\n\nPranadeep sends an image and says: " + (msg or "What do you see?")
            response = gemini_vision.generate_content([prompt, image_part])
            raw = response.text
        except: pass

    # Gemini Pro
    if not raw:
        try:
            chat_session = gemini_model.start_chat(history=[
                {"role": "user" if h["role"] == "user" else "model",
                 "parts": [h["content"]]} for h in history
            ])
            response = chat_session.send_message(system + "\n\nPranadeep says: " + (msg or ""))
            raw = response.text
        except: pass

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

@app.route('/knowledge', methods=['GET'])
def get_knowledge_endpoint():
    """View everything JARVIS knows"""
    if not db:
        return jsonify({'error': 'no database'})
    try:
        doc = db.collection('knowledge').document('personal').get()
        if doc.exists:
            return jsonify(doc.to_dict())
        return jsonify({'message': 'no knowledge yet'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/knowledge', methods=['POST'])
def update_knowledge():
    """Directly update knowledge"""
    if not db:
        return jsonify({'error': 'no database'})
    try:
        data = request.json
        db.collection('knowledge').document('personal').set(data, merge=True)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/reset', methods=['POST'])
def reset():
    sid = request.json.get('session_id', 'default')
    if db:
        try: db.collection('sessions').document(sid).delete()
        except: pass
    convos.pop(sid, None)
    return jsonify({'ok': True})

@app.route('/health')
def health():
    return jsonify({
        'status': 'online',
        'ai': 'gemini-1.5-pro+groq',
        'vision': 'enabled',
        'memory': 'firebase' if db else 'in-memory',
        'knowledge': 'enabled',
        'timezone': 'IST'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
