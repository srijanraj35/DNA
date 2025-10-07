import os
import sqlite3
import random
import requests # Included for potential future Ollama/AI integration
import json
from flask import Flask, render_template, request, url_for, redirect, session, g, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

# --- Configuration and Setup ---

app = Flask(__name__)
# Set a strong secret key for session management
app.secret_key = 'your_super_secret_key_for_flask_sessions'
DATABASE = 'database/wellness.db'

# --- Database Initialization and Utility Functions ---

def get_db():
    """Opens a new database connection for the current application context."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row 
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Closes the database connection at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initializes the database schema with all required tables."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # 1. Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                badge_number TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                rank TEXT NOT NULL
            );
        ''')
        
        # 2. Wellness Stats Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wellness_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                stress_level INTEGER, 
                mood TEXT, 
                sleep_hours REAL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE (user_id, date)
            );
        ''')

        # 3. Journal Entries Table (The one causing the error)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                content TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
                UNIQUE (user_id, date) 
            );
        ''')
        db.commit()

# Call initialization immediately to ensure tables exist
init_db()

# --- AI Simulation Data and Logic ---


QUOTES = [
    "The most resilient armor is a clear mind. - System Log 404",
    "Yesterday's anomaly is tomorrow's baseline. Adapt and process. - Sentinel Protocol",
    "Your neural network is mission-critical. Maintenance is mandatory. - AI Core",
    "Error 404: Burnout Not Found. Optimize your life code. - Debug Mode",
    "The strength of the shield is in the operator's well-being. - Directive 01",
]

def ai_identify_stress(answers, sleep_hours):
    """Simulates AI identifying stress level (1-5) based on interactive answers and sleep."""
    base_stress = 2 
    
    for index, answer in answers.items():
        q_data = INTERACTIVE_QUESTIONS[int(index)]
        if q_data['negative_impact'] and answer == 'yes':
            base_stress += q_data['score']
        elif not q_data['negative_impact'] and answer == 'no':
            base_stress += q_data['score']
    
    if sleep_hours < 5.0:
        base_stress += 2 
    elif sleep_hours < 7.0:
        base_stress += 1 

    stress_level = max(1, min(5, base_stress))
    
    mood_map = {1: 'optimized', 2: 'stable', 3: 'fatigued', 4: 'strained', 5: 'critical'}
    mood = mood_map.get(stress_level, 'fatigued')

    if stress_level >= 4:
        recommendation = "**CRITICAL STRESS ALERT.** Immediate systemic cooldown recommended."
    elif stress_level == 3:
        recommendation = "**STABILITY WARNING.** Elevated cognitive load detected. Focus on rest."
    else:
        recommendation = "**SYSTEMS OPTIMAL.** Continue preventative maintenance."

    return stress_level, mood, recommendation

def generate_ai_recommendation(stress_level, mood):
    """Generates a brief recommendation for dashboard refresh without full check-in."""
    stress_map = {1: 'optimal', 2: 'stable', 3: 'elevated', 4: 'high', 5: 'critical'}
    level_name = stress_map.get(stress_level, 'elevated').upper()

    if stress_level >= 4:
        return f"**LEVEL {level_name} ALERT:** Your cognitive strain is critical. Engage the **Peer-AI Chatbot** now."
    elif stress_level == 3:
        return f"**LEVEL {level_name} WARNING:** Detected elevated mental fatigue ({mood}). Prioritize sleep."
    else:
        return f"**STATUS OPTIMAL:** Wellness profile ({mood}) stable."


# --- Before Request Hook (Session/Auth Management) ---

@app.before_request
def check_user_logged_in():
    """Sets a global variable 'g.user' if the user is logged in."""
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        db = get_db()
        g.user = db.execute('SELECT id, full_name, email,rank FROM users WHERE id = ?', (user_id,)).fetchone()

# --- Auth Routes ---

@app.route('/')
def index():
    """Redirects authenticated users to dashboard, others to login."""
    if g.user:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=('GET', 'POST'))
def register():
    """Handles user registration."""
    if g.user:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        full_name = request.form['full_name']
        badge_number = request.form['badge_number']
        email = request.form['email']
        password = request.form['password']
        rank = request.form['rank']
        
        if not all([full_name, badge_number, email, password]):
            flash('All fields are required!', 'error')
            return render_template('register.html')

        password_hash = generate_password_hash(password)
        db = get_db()
        error = None

        try:
            db.execute(
                "INSERT INTO users (full_name, badge_number, email, password_hash, rank) VALUES (?, ?, ?, ?, ?)",
                (full_name, badge_number, email, password_hash, rank),
            )
            db.commit()
        except sqlite3.IntegrityError:
            error = "User with that email or badge number already exists."
            flash(error, 'error')
            session.clear()
            return render_template('register.html')

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    """Handles user login."""
    if g.user:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        error = None
        
        user = db.execute(
            'SELECT * FROM users WHERE email = ?', (email,)
        ).fetchone()

        if user is None or not check_password_hash(user['password_hash'], password):
            error = 'Access Denied: Incorrect credentials.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            g.user = db.execute('SELECT id, full_name, email FROM users WHERE id = ?', (user['id'],)).fetchone()
            return redirect(url_for('dashboard'))
        
        flash(error, 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Clears the session and logs the user out."""
    session.clear()
    flash('System access terminated. Logout successful.', 'success')
    return redirect(url_for('login'))

# -----------------------------------------------
# Dashboard Data and Chart Generation
# -----------------------------------------------

@app.route('/submit_interactive_status', methods=['POST'])
def submit_interactive_status():
    """Handles the submission from the dynamic check-in form, runs AI analysis, and saves data."""
    if not g.user:
        return jsonify({'success': False, 'message': 'Authentication required.'}), 401

    try:
        data = request.get_json()
        user_id = g.user['id']
        answers = data.get('answers', {})
        sleep_hours = float(data.get('sleep_hours', 7.0))
        today_date = datetime.now().strftime('%Y-%m-%d')

        stress_level, mood, ai_recommendation = ai_identify_stress(answers, sleep_hours)
        
        db = get_db()
        db.execute('''
            INSERT INTO wellness_stats (user_id, date, stress_level, mood, sleep_hours) 
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                stress_level=excluded.stress_level, 
                mood=excluded.mood, 
                sleep_hours=excluded.sleep_hours
        ''', (user_id, today_date, stress_level, mood, sleep_hours))
        db.commit()

        return jsonify({
            'success': True,
            'message': 'Status uploaded and analyzed.',
            'stress_level': stress_level,
            'mood': mood,
            'ai_recommendation': ai_recommendation
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Data Processing Error: {e}'}), 500

@app.route('/dashboard')
def dashboard():
    """The main user dashboard, fetching stats for display."""
    if not g.user:
        flash('System requires login protocol access.', 'error')
        return redirect(url_for('login'))

    user_id = g.user['id']
    db = get_db()
    today = datetime.now()
    today_date = today.strftime('%Y-%m-%d')
    
    current_stats = db.execute(
        'SELECT * FROM wellness_stats WHERE user_id = ? AND date = ?', 
        (user_id, today_date)
    ).fetchone()

    stress_level = current_stats['stress_level'] if current_stats else 3
    mood = current_stats['mood'] if current_stats else 'stable'
    sleep_hours = current_stats['sleep_hours'] if current_stats else 7.0 

    ai_recommendation = generate_ai_recommendation(stress_level, mood)
    daily_quote = random.choice(QUOTES)

    # 1. Fetch 7-Day Stress Trend Data (Last 7 days, chronologically)
    stress_trend_data = db.execute('''
        SELECT date, stress_level FROM wellness_stats 
        WHERE user_id = ? AND date >= ? 
        ORDER BY date ASC
    ''', (user_id, (today - timedelta(days=6)).strftime('%Y-%m-%d'))).fetchall()

    data_map = {item['date']: item['stress_level'] for item in stress_trend_data}
    chart_labels = []
    chart_data = []

    # 2. Generate the 7 chronological dates ending today
    dates_list = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]

    # 3. Build the Labels and Data Arrays
    for date_str in dates_list:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        chart_labels.append(date_obj.strftime('%a')) 
        chart_data.append(data_map.get(date_str, None))

    # 4. Reorder Arrays to Visually Start at Monday
    try:
        mon_index = chart_labels.index('Mon') 
    except ValueError:
        mon_index = 0 
        
    chart_labels = chart_labels[mon_index:] + chart_labels[:mon_index]
    chart_data = chart_data[mon_index:] + chart_data[:mon_index]
    
    flash("Please Complete Tasks")
    
    # 5. Pass all necessary data
    return render_template(
        'dashboard.html',
        full_name=g.user['full_name'],
        rank=g.user['rank'],
        stress_level=stress_level,
        mood=mood,
        sleep_hours=sleep_hours,
        ai_recommendation=ai_recommendation,
        daily_quote=daily_quote,
        chart_labels=chart_labels,
        chart_data=chart_data,
        today_date=today.strftime('%A, %B %d, %Y'),
    )

# -----------------------------------------------
# Journal Routes
# -----------------------------------------------

@app.route('/journal', methods=['GET', 'POST'])
def journal():
    """Handles displaying and submitting new journal entries and passing header context."""
    if not g.user:
        flash('System requires login protocol access.', 'error')
        return redirect(url_for('login'))

    user_id = g.user['id']
    db = get_db()
    today = datetime.now()
    date_only_str = today.strftime('%Y-%m-%d')

    # 1. Handle Journal Submission (POST)
    if request.method == 'POST':
        content = request.form.get('content')
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if content:
            try:
                db.execute(
                    "INSERT INTO journal_entries (user_id, date, content) VALUES (?, ?, ?)",
                    (user_id, current_datetime, content)
                )
                db.commit()
                flash('Journal entry saved securely!', 'success')
            except Exception as e:
                flash(f'Error saving journal: {e}', 'error')
        else:
            flash('Journal content cannot be empty.', 'error')
            
        return redirect(url_for('journal'))

    # --- Data for Header and Journal Content (GET) ---

    # 2. Fetch User's Latest Stress/Mood Status (For Header/Stress Index Display)
    current_stats = db.execute(
        'SELECT stress_level, mood FROM wellness_stats WHERE user_id = ? ORDER BY date DESC LIMIT 1', 
        (user_id,)
    ).fetchone()
    
    # Define variables required by the HTML header
    stress_level = current_stats['stress_level'] if current_stats else 3
    mood = current_stats['mood'] if current_stats else 'stable' 
    
    # 3. Fetch all previous Journal Entries
    entries = db.execute(
        'SELECT * FROM journal_entries WHERE user_id = ? ORDER BY date DESC',
        (user_id,)
    ).fetchall()
    
    formatted_entries = []
    for entry in entries:
        date_obj = datetime.strptime(entry['date'], '%Y-%m-%d %H:%M:%S')
        formatted_entries.append({
            'content': entry['content'],
            'date': date_obj.strftime('%B %d, %Y - %H:%M')
        })

    # 4. Pass only the required data
    return render_template(
        'journal.html',
        # --- ESSENTIAL HEADER/USER CONTEXT ---
        full_name=g.user['full_name'],
        rank=g.user['rank'], # Assuming 'rank' is available in g.user
        today_date=today.strftime('%A, %B %d, %Y'),
        stress_level=stress_level,
        mood=mood,
        
        # --- JOURNAL SPECIFIC DATA ---
        entries=formatted_entries,
        
        # --- Pass placeholders for layout consistency (Optional but safer) ---
        ai_recommendation="",
        daily_quote="",
        chart_labels=[],
        chart_data=[],
    )

# -----------------------------------------------
# Survey Routes
# -----------------------------------------------

@app.route('/survey')
def survey():
    """The main user survey, fetching stats for display."""
    if not g.user:
        flash('System requires login protocol access.', 'error')
        return redirect(url_for('login'))

    user_id = g.user['id']
    db = get_db()
    today = datetime.now()
    today_date = today.strftime('%Y-%m-%d')
    
    current_stats = db.execute(
        'SELECT * FROM wellness_stats WHERE user_id = ? AND date = ?', 
        (user_id, today_date)
    ).fetchone()

    stress_level = current_stats['stress_level'] if current_stats else 3
    mood = current_stats['mood'] if current_stats else 'stable'
    sleep_hours = current_stats['sleep_hours'] if current_stats else 7.0 

    ai_recommendation = generate_ai_recommendation(stress_level, mood)
    daily_quote = random.choice(QUOTES)

    # 1. Fetch 7-Day Stress Trend Data (Last 7 days, chronologically)
    stress_trend_data = db.execute('''
        SELECT date, stress_level FROM wellness_stats 
        WHERE user_id = ? AND date >= ? 
        ORDER BY date ASC
    ''', (user_id, (today - timedelta(days=6)).strftime('%Y-%m-%d'))).fetchall()

    data_map = {item['date']: item['stress_level'] for item in stress_trend_data}
    chart_labels = []
    chart_data = []

    # 2. Generate the 7 chronological dates ending today
    dates_list = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]

    # 3. Build the Labels and Data Arrays
    for date_str in dates_list:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        chart_labels.append(date_obj.strftime('%a')) 
        chart_data.append(data_map.get(date_str, None))

    # 4. Reorder Arrays to Visually Start at Monday
    try:
        mon_index = chart_labels.index('Mon') 
    except ValueError:
        mon_index = 0 
        
    chart_labels = chart_labels[mon_index:] + chart_labels[:mon_index]
    chart_data = chart_data[mon_index:] + chart_data[:mon_index]
    
    # 5. Pass all necessary data
    return render_template(
        'survey.html',
        full_name=g.user['full_name'],
        rank=g.user['rank'],
        stress_level=stress_level,
        mood=mood,
        sleep_hours=sleep_hours,
        ai_recommendation=ai_recommendation,
        daily_quote=daily_quote,
        chart_labels=chart_labels,
        chart_data=chart_data,
        today_date=today.strftime('%A, %B %d, %Y'),
    )



@app.route("/submit-survey", methods=["POST"])
def submit_survey():
    data = request.get_json()
    answers = data.get("answers", [])  # Expecting [1,0,1,1]
    print("✅ Received answers:", answers)  # 👈 You'll see this in terminal
    return jsonify({"success": True, "message": "Survey received!"})



# -----------------------------------------------
# Wearables Routes
# -----------------------------------------------

@app.route('/submit_wearables_data', methods=['POST'])
def submit_wearables_data():
    """Receives health metrics from the wearables form and processes them."""
    if not g.user:
        return jsonify({'success': False, 'message': 'Authentication required.'}), 401
    
    try:
        # Get data directly from the form submission
        temp = request.form.get('body_temp', type=float)
        oxygen = request.form.get('blood_oxygen', type=float)
        sleep = request.form.get('hours_sleep', type=float)
        hr = request.form.get('heart_rate', type=int)
        
        # Simple validation
        if None in [temp, oxygen, sleep, hr]:
            return jsonify({'success': False, 'message': 'Missing required metric data.'}), 400

        # --- Data Logging (Simulation) ---
        print("\n✅ WEARABLES DATA RECEIVED:")
        print(f"User: {g.user['full_name']}")
        print(f"Temperature: {temp}°C | Oxygen: {oxygen}%")
        print(f"Sleep: {sleep}h | Heart Rate: {hr} BPM")
        print("--------------------------------\n")
        # In a real app, you would save this to a new 'health_metrics' DB table.

        flash('Wearables data recorded successfully.', 'success')
        return redirect(url_for('wearables')) # Redirect to prevent form resubmission

    except Exception as e:
        flash(f'Error processing data: {e}', 'error')
        return redirect(url_for('wearables'))


# --- Link to the New Route ---
@app.route('/wearables')
def wearables():
    """Renders the Wearables data input page."""
    if not g.user:
        return redirect(url_for('login'))
        
    # Pass dashboard context data (simplified for this view)
    today = datetime.now()
    today_date = today.strftime('%A, %B %d, %Y')



    # You need to pass the minimal variables required by the header/script
    return render_template(
        'wearables.html', 
        full_name=g.user['full_name'],
        rank=g.user['rank'],
        stress_level=3, # Default placeholder
        mood='stable',   # Default placeholder
        today_date=today_date,
        # Pass placeholder data required by the dashboard layout/script
        chartLabels=[], chartData=[], ai_recommendation="", daily_quote=""
    )



# -----------------------------------------------
# Audio Routes
# -----------------------------------------------


# --- Configuration (Add near the top with UPLOAD_FOLDER definition) ---
UPLOAD_FOLDER = 'static/audios'
ALLOWED_EXTENSIONS = {'mp3', 'wav'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload directory exists upon startup (critical for file saving)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Checks if the uploaded file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# -----------------------------------------------
# Audio Routes (Place this section near the Wearables Routes)
# -----------------------------------------------

@app.route('/audio', methods=['GET', 'POST'])
def audio():
    """Handles file upload (POST) and renders the audio library (GET)."""
    if not g.user:
        flash('Authentication required for file uploads.', 'error')
        return redirect(url_for('login'))
    
    # 1. Handle File Upload Logic (POST Request)
    if request.method == 'POST':
        # Check for file presence
        if 'audio' not in request.files:
            flash('No file part in the request.', 'error')
            return redirect(url_for('audio'))
        
        file = request.files['audio']
        
        if file.filename == '':
            flash('No selected file.', 'error')
            return redirect(url_for('audio'))
        
        if file and allowed_file(file.filename):
            # Sanitize filename for security
            filename = secure_filename(file.filename)
            # Save the file
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            print(f"\n✅ FILE SAVED. SERVER PATH: {file_path}\n")
            
            # NOTE: In a real application, you would log file_path, filename, and user_id to a database table here.
            
            flash(f'File "{filename}" uploaded successfully.', 'success')
        else:
            flash('Invalid file type. Only MP3 and WAV are allowed.', 'error')
            
        return redirect(url_for('audio'))

    # 2. Handle Audio Library Display (GET Request)
    
    # List all files currently in the folder
    audios = os.listdir(app.config['UPLOAD_FOLDER'])
    
    # Pass dashboard context data (simplified for this view)
    today = datetime.now()
    today_date = today.strftime('%A, %B %d, %Y')
    
    # Determine the status for the header display (simplified)
    stress_level = g.user['stress_level'] if g.user and 'stress_level' in g.user else 3
    
    return render_template(
        'audio.html', 
        audios=audios,
        full_name=g.user['full_name'],
        rank=g.user['rank'],
        stress_level=stress_level,
        mood='stable',
        today_date=today_date,
        
        # Pass placeholder data required by the dashboard layout/script
        chartLabels=[], chartData=[], ai_recommendation="", daily_quote=""
    )

# --- Link the main '/audio' URL to the upload function ---
@app.route('/audio')
def audio_page():
    return redirect(url_for('audio'))





# -----------------------------------------------
# Chatbot and Test Data Routes
# -----------------------------------------------

@app.route('/chatbot_response', methods=['POST'])
def chatbot_response():
    """Simulates a response from the stress-reduction AI Chatbot with multi-turn memory."""
    if not g.user:
        return jsonify({'response': "Error: Authentication system offline."})

    try:
        data = request.get_json()
        user_message = data.get('message', '').lower()
        user_id = g.user['id']
        
        if 'chatbot_context' not in session:
             session['chatbot_context'] = {'state': 'initial', 'protocol': None}
             
        context = session['chatbot_context']
        reply = ""

        # --- Core Protocol Selection ---
        if context['state'] == 'initial':
            if 'stress' in user_message or 'anxiety' in user_message or 'tired' in user_message:
                context['state'] = 'protocol_requested'
                reply = "Stress/Fatigue identified. Please select a Wellness Protocol: **[1] Decompression Breathing**, **[2] Mood Logging**, or **[3] Peer Connect Inquiry**."
            
            elif 'help' in user_message or 'protocol' in user_message:
                reply = "Wellness Protocols: **[1] Decompression Breathing**, **[2] Mood Logging**, **[3] Peer Connect Inquiry**. Type the number or protocol name to begin."
            
            elif 'status' in user_message:
                current_stats = get_db().execute('SELECT stress_level, mood FROM wellness_stats WHERE user_id = ? ORDER BY date DESC LIMIT 1', (user_id,)).fetchone()
                if current_stats:
                    reply = f"Current Status Report: Stress Level **{current_stats['stress_level']}/5**. Mood: **{current_stats['mood'].upper()}**. How does this align with your perceived state?"
                else:
                    reply = "Current Status: Data insufficient. Please complete your daily check-in."
            
            else:
                reply = "Awaiting command. State your current emotional status or request a protocol (e.g., 'Breathing', 'Status')."

        # --- Protocol Selection State ---
        elif context['state'] == 'protocol_requested':
            if '1' in user_message or 'breath' in user_message:
                context['state'] = 'breathing_active'
                context['protocol'] = 'breathing'
                reply = "Breathing Protocol selected. Focus on the green wave visual. You are safe. You are stable. **Type 'END' when finished.**"
            
            elif '2' in user_message or 'log' in user_message:
                context['state'] = 'logging_active'
                context['protocol'] = 'logging'
                reply = "Mood Logging selected. Please type a summary of your three most impactful emotions today. **Type 'END' when finished.**"
                
            elif '3' in user_message or 'peer' in user_message:
                context['state'] = 'initial' 
                reply = "Peer Connect Inquiry: Access the Quick Actions panel for the secure Peer Network portal. I cannot initiate that connection directly."
            
            else:
                context['state'] = 'initial' 
                reply = "Invalid selection. Resetting state. Please request a protocol or status."

        # --- Active Protocol State ---
        elif context['state'] in ['breathing_active', 'logging_active']:
            if 'end' in user_message:
                context['state'] = 'initial'
                context['protocol'] = None
                reply = "Protocol concluded. Remember to prioritize self-maintenance. Status is now **INITIAL.**"
            elif context['protocol'] == 'logging':
                 # In a real app, this data would be stored in a journal DB table
                 print(f"User {g.user['full_name']} logged: {user_message}")
                 reply = "Log recorded. Your data has been securely filed. Continue your thoughts, or **Type 'END'.**"
            else:
                 reply = f"System is currently running the {context['protocol'].upper()} Protocol. Please continue or **Type 'END'** to conclude."

        
        session['chatbot_context'] = context
        
        return jsonify({'response': reply})

    except Exception as e:
        print(f"Server-side Chatbot Error: {e}")
        return jsonify({'response': "ERROR: Server processing failure. Check console."}), 500

@app.route('/test_data/generate', methods=['GET'])
def generate_fake_data():
    """Generates 14 days of randomized fake wellness data for testing charts and trends."""
    if not g.user:
        flash('You must be logged in to generate test data.', 'error')
        return redirect(url_for('login'))

    user_id = g.user['id']
    db = get_db()
    
    moods_map = {
        1: ['optimized', 'stable'],
        2: ['stable', 'fatigued'],
        3: ['fatigued', 'strained'],
        4: ['strained', 'critical'],
        5: ['critical']
    }
    
    for i in range(14):
        date = datetime.now() - timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        
        # 1. GENERATE STRESS (Randomly skewed towards the middle)
        stress_choices = [1, 2, 3, 4, 5]
        stress_weights = [0.1, 0.25, 0.3, 0.25, 0.1]
        stress = random.choices(stress_choices, weights=stress_weights, k=1)[0]
        
        # 2. GENERATE SLEEP (Correlate with stress, but add randomness)
        if stress >= 4:
            sleep = round(random.uniform(5.0, 6.5), 1)
        elif stress <= 2:
            sleep = round(random.uniform(7.5, 9.0), 1)
        else:
            sleep = round(random.uniform(6.5, 8.0), 1)
            
        # 3. GENERATE MOOD (Based on the generated stress level)
        mood = random.choice(moods_map.get(stress, ['stable']))

        try:
            db.execute('''
                INSERT INTO wellness_stats (user_id, date, stress_level, mood, sleep_hours) 
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, date) DO UPDATE SET
                    stress_level=excluded.stress_level, 
                    mood=excluded.mood, 
                    sleep_hours=excluded.sleep_hours
            ''', (user_id, date_str, stress, mood, sleep))
        except Exception as e:
            db.rollback()
            flash(f'Database error during test data generation: {e}', 'error')
            return redirect(url_for('dashboard'))

    db.commit()
    flash('14 days of randomized test data generated successfully! Check your chart.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/test_data/clear', methods=['GET'])
def clear_user_data():
    """Clears all wellness data for the logged-in user."""
    if not g.user:
        flash('You must be logged in to clear data.', 'error')
        return redirect(url_for('login'))
    
    db = get_db()
    db.execute('DELETE FROM wellness_stats WHERE user_id = ?', (g.user['id'],))
    db.commit()
    flash('All your previous wellness data has been cleared.', 'success')
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    # init_db() is already called outside of this block
    app.run(debug=True)