import sqlite3
import random
import requests 
import json
from flask import Flask, render_template, request, url_for, redirect, session, g, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date
import os
import pickle
import numpy 
import pandas
import sklearn
import nltk
from nltk.corpus import stopwords
import string
from nltk.stem.porter import PorterStemmer
import smtplib
from email.message import EmailMessage
import sys


class backend():
    def __init__(self, app):
        self.DATABASE = 'database/userData.db'
        self.app = app

    def init_db(self):
        with self.app.app_context():
            db = self.get_db()
            cursor = db.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    badge_no TEXT UNIQUE NOT NULL,
                    rank TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                );''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS final_stats (
                    badge_no INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    stress_level INTEGER 
                );
            ''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS journal(
                        badge_no INTEGER NOT NULL,
                        date TEXT NOT NULL,
                        data TEXT,
                        stress_level INTEGER
                        );''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS survey(
                            badge_no INTEGER NOT NULL,
                            date TEXT NOT NULL,
                           q1 INTEGER,q2 INTEGER, q3 INTEGER, q4 INTEGER, q5 INTEGER,
                           stress_level INTEGER);
                            ''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS wearables(
                           badge_no INTEGER NOT NULL,
                            date TEXT NOT NULL,
                           body_temperature DOUBLE,
                           blood_oxygen DOUBLE, 
                           hours_of_sleep DOUBLE,
                           heart_rate DOUBLE, 
                           stress_level INTEGER);''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS audio(
                              badge_no INTEGER NOT NULL,
                        date TEXT NOT NULL,
                        stress_level INTEGER);''')
            db.commit()

    def get_db(self):
        db = getattr(g, '_database', None)
        if db is None:
            db = g._database = sqlite3.connect(self.DATABASE, timeout=10, check_same_thread=False)
            db.row_factory = sqlite3.Row 
        return db

    def Register(self, full_name, badge_number, rank, email, password):
        if not all([full_name, badge_number, rank, email, password]):
            flash('All fields are required!', 'error')
            return render_template('register.html')
        password_hash = generate_password_hash(password)
        db = self.get_db()
        error = None

        try:
            db.execute(
                "INSERT INTO users (full_name, badge_no, rank, email, password_hash) VALUES (?, ?, ?, ?, ?)",
                (full_name, badge_number, rank, email, password_hash),
            )
            db.commit()
            return True
        except sqlite3.IntegrityError:
            error = "User with that email or badge number already exists."
            flash(error, 'error')
            return render_template('register.html')
        
    def Login(self, email, password):
        db = self.get_db()
        error = None
        
        user = db.execute(
            'SELECT * FROM users WHERE email = ?', (email,)
        ).fetchone()

        if user is None or not check_password_hash(user['password_hash'], password):
            error = 'Access Denied: Incorrect credentials.'

        if error is None:
            session.clear()
            session['badge_no'] = user['badge_no']
            session['rank'] = user['rank']
            session['sent_email'] = 0
            g.user = db.execute('SELECT  full_name, email, rank FROM users WHERE badge_no = ?', (user['badge_no'],)).fetchone()
            return redirect(url_for('dashboard'))
        
        flash(error, 'error')
        return render_template('login.html')
    
    def transform_text(self, text):
        text = text.lower()
        text = nltk.word_tokenize(text)

        y = []
        for i in text:
            if i.isalnum():
                y.append(i)

        text = y[:]
        y.clear()

        for i in text:
            if i not in stopwords.words('english') and i not in string.punctuation:
                y.append(i)
                
        text = y[:]
        y.clear()
        
        ps = PorterStemmer()
        for i in text:
            try:
                t = ps.stem(i) 
                y.append(t)
            except:
                y.append(i)
        
        return " ".join(y)

    def model1(self, data):
        try:
            model = pickle.load(open('models\journal_based\Journal_based_model.pkl', 'rb'))
            vectorizer = pickle.load(open('models\journal_based\Vectorizer.pkl', 'rb'))

            data = b.transform_text(data)
            v = vectorizer.transform([data])
            result = int(model.predict(v)[0]) 

            return result
        except FileNotFoundError:
            print("WARNING: ML Model files not found. Using default stress level of 5.")
            return 0
        except Exception as e:
            print(f"ERROR: Model prediction failed: {e}. Using default stress level of 5.")
            return 0
        
        
    def model2(self, bt, bo, s, hr):
        scaler = pickle.load(open('models\wearables_based\scaler.pkl', 'rb'))
        model = pickle.load(open('models\wearables_based\wearable_based_model.pkl', 'rb'))

        x = [bt, bo, s, hr]

        v = scaler.transform([x])
        result = model.predict(v)

        return result

    
    def get_stress_index(self):
        stress_index = 0
        d = date.today()
        db = self.get_db()
        temp = db.execute("SELECT * from final_stats WHERE badge_no = ? AND date = ?", (session['badge_no'], date.today())).fetchone()
        if temp:
            return temp['stress_level']
        
        row = db.execute("SELECT stress_level from survey WHERE badge_no = ? and date = ?", (session['badge_no'], d)).fetchone()
        survey_stress = row['stress_level'] if row else 0

        row1 = db.execute("SELECT stress_level from journal WHERE badge_no = ? and date = ?", (session['badge_no'], d)).fetchone()
        journal_stress = row1['stress_level'] if row1 else 0

        row2 = db.execute("SELECT stress_level from wearables WHERE badge_no = ? and date = ?", (session['badge_no'], d)).fetchone()
        wearables_stress = row2['stress_level'] if row2 else 0

        row3 = db.execute("SELECT stress_level from  audio WHERE badge_no = ? and date = ?", (session['badge_no'], d)).fetchone()
        audio_stress = row3['stress_level'] if row3 else 0

        stress_index = (survey_stress/5)+(journal_stress*3)+(wearables_stress+1 if wearables_stress>0 else 0)+(audio_stress)
        return stress_index
    

    def get_weekly_data(self):
        db = self.get_db()
        weekly_data = []

        today = date.today()
        current_day_index = today.weekday() 

        monday_date = today - timedelta(days=current_day_index)

        for i in range(7):
            day_date = monday_date + timedelta(days=i)
            row = db.execute(
                "SELECT stress_level FROM final_stats WHERE badge_no = ? AND date = ?",
                (session['badge_no'], day_date)
            ).fetchone()
            weekly_data.append(row['stress_level'] if row else 0)

        return weekly_data

        
    def get_stress_average(self):
        db = self.get_db()
        d = date.today()
        row = db.execute("SELECT stress_level FROM final_stats WHERE badge_no = ? AND date = ?", (session['badge_no'], d)).fetchone()
        stress = row['stress_level'] if row else 0

        if stress >= 9:
            return "Critical"
        elif stress >6:
            return "Highly Stressed"
        elif stress > 4:
            return "Moderatley Stressed"
        else:
            return "Not Stressed"
        
    def get_recommendations(self):
        recommendations = {
    1: [
        "Keep doing what you’re doing — you’re managing stress well.",
        "Go for a short walk or stretch during breaks.",
        "Listen to your favorite music or podcast.",
        "Maintain a healthy sleep schedule.",
        "Express gratitude or write one positive thought daily."
    ],
    2: [
        "Stay consistent with your routines.",
        "Do a quick mindfulness exercise after waking up.",
        "Spend time outdoors for at least 10 minutes daily.",
        "Enjoy a hobby or creative activity.",
        "Stay hydrated and eat on time."
    ],
    3: [
        "Take 10–15 minutes daily for deep breathing or meditation.",
        "Limit caffeine or energy drink intake.",
        "Try light physical activity like yoga or cycling.",
        "Avoid multitasking — focus on one thing at a time.",
        "Talk with friends or colleagues about your day."
    ],
    4: [
        "Practice mindfulness or meditation during breaks.",
        "Plan your day ahead to avoid last-minute stress.",
        "Unplug from your phone for 30 minutes before bed.",
        "Do breathing exercises when you feel tense.",
        "Reward yourself for small accomplishments."
    ],
    5: [
        "Schedule short relaxation breaks throughout your day.",
        "Reduce social media/news exposure if it’s overwhelming.",
        "Practice journaling — write down what’s bothering you.",
        "Eat regular, balanced meals.",
        "Get some good sleep"
    ],
    6: [
        "Balance work and rest — don’t skip meals or breaks.",
        "Talk to someone you trust about what’s stressing you.",
        "Engage in a hobby that calms your mind.",
        "Stretch or walk after long work sessions.",
        "Get some good sleep"
    ],
    7: [
        "Take a full day off or a few hours to disconnect from work.",
        "Do grounding exercises — focus on breathing or your senses.",
        "Seek support from a trusted person or counselor.",
        "Do light exercise to release tension.",
        "Get some good sleep"
    ],
    8: [
        "Speak to a mental health professional if stress feels overwhelming.",
        "Avoid negative self-talk; remind yourself this phase will pass.",
        "Try progressive muscle relaxation or deep breathing.",
        "Spend time in nature or a peaceful environment.",
        "Get some good sleep"
    ],
    9: [
        "Reach out for professional help immediately.",
        "Take time away from stressful environments if possible.",
        "Avoid making major life decisions until you feel stable.",
        "Engage in calming activities — art, music, or prayer.",
        "Focus on slow breathing and grounding exercises.",
        "Get some good sleep"
    ],
    10: [
        "Seek urgent professional support or counseling.",
        "Talk to a trusted friend, family member, or helpline.",
        "Disconnect completely from work and stressors temporarily.",
        "Practice deep breathing or meditation multiple times daily.",
        "Get some good sleep"
    ]
}

        db = self.get_db()
        d = date.today()
        temp = []
        row_stress = db.execute("SELECT stress_level FROM final_stats WHERE badge_no = ? AND date = ?", (g.user['badge_no'], d)).fetchone()
        stress_index = row_stress['stress_level'] if row_stress else 1

        row_sleep = db.execute("SELECT hours_of_sleep FROM wearables WHERE badge_no = ? AND date = ?", (g.user['badge_no'], d)).fetchone()
        sleep = row_sleep['hours_of_sleep'] if row_sleep else 7

        for i in range(1, 11):
            if sleep < 4 and stress_index == i:
                temp.append(recommendations[i][0])
                temp.append(recommendations[i][4])
                return "\n".join(temp)
            if stress_index == i:
                temp.append(recommendations[i][0])
                temp.append(recommendations[i][1])
                return "\n".join(temp)
            
    def get_weekly_journal(self):
        db = self.get_db()
        weekly_data = []

        today = date.today()
        current_day_index = today.weekday() 

        monday_date = today - timedelta(days=current_day_index)

        for i in range(7):
            day_date = monday_date + timedelta(days=i)
            row = db.execute(
                "SELECT * FROM journal WHERE badge_no = ? AND date = ?",
                (session['badge_no'], day_date)
            ).fetchone()
            weekly_data.append(row['data'] if row else "")

        return weekly_data
    
    def update_journal(self, data, date):
        db = self.get_db()
        stress = self.model1(data) 

        try:
            existing = db.execute("SELECT * FROM journal WHERE badge_no = ? AND date = ?", (session['badge_no'], date)).fetchone() 
        
            if existing:
                db.execute("UPDATE journal SET data = ? , stress_level = ? WHERE badge_no = ? AND  date = ?", (data, stress, session['badge_no'], date))
            else:
                db.execute("INSERT into journal VALUES(?, ?, ?, ?)", (session['badge_no'], date, data, stress))

            db.commit()
            if stress == 1:
                flash("Stressed") 
            else:
                flash("Not stressed")
        except Exception as e:
            print(f"DATABASE ERROR during update_journal: {e}")
            db.rollback() 
            flash('SYSTEM ERROR: Could not save journal entry. Database failure.', 'error')

    def get_all_journal_entries(self):
        db = self.get_db()
    
        entries = db.execute(
            "SELECT date, data FROM journal WHERE badge_no = ? ORDER BY date DESC",
            (session['badge_no'],)
        ).fetchall()
        
        return [
            {'date': row['date'], 'content': row['data']} 
            for row in entries
        ]
    
    def update_survey(self, data, stress):
        db = self.get_db()
        existing = db.execute("SELECT * FROM survey WHERE badge_no = ? and date = ?",(session['badge_no'], date.today().strftime('%Y-%m-%d'))).fetchone()
        if existing:
            db.execute("UPDATE survey SET q1=?, q2 = ?, q3 = ?, q4 = ?, q5 = ?, stress_level = ? WHERE date = ? AND badge_no = ?",(data[0], data[1], data[2], data[3], data[4], stress, date.today().strftime('%Y-%m-%d'), session['badge_no']))
        else:
            db.execute("INSERT INTO survey VALUES(?, ?, ?, ?, ?, ?, ?, ?)",(session['badge_no'], date.today().strftime('%Y-%m-%d'), data[0], data[1], data[2], data[3], data[4], stress))
        db.commit()

    def update_wearables(self, bt, bo, s, hr):
        db = self.get_db()
        stress = self.model2(bt, bo, s, hr)
        stress = int(stress)
        existing = db.execute("SELECT * FROM wearables WHERE badge_no = ? AND date = ?", (session['badge_no'], date.today().strftime('%Y-%m-%d'))).fetchone()
        if existing:
            db.execute("UPDATE wearables SET body_temperature = ? , blood_oxygen = ?, hours_of_sleep = ?, heart_rate = ?, stress_level = ? WHERE badge_no = ? AND date = ?", (bt, bo, s, hr, stress, session['badge_no'], date.today().strftime('%Y-%m-%d')))
        else:
            db.execute("INSERT INTO wearables VALUES(?, ?, ?, ?, ?, ?, ?)", (session['badge_no'], date.today().strftime('%Y-%m-%d'), bt, bo, s, hr, stress))
        db.commit()
        if stress == 3:
            flash("Highly Stressed")
        elif stress == 2:
            flash("Moderately Stressed")
        else:
            flash("Not stressed")



    def update_final(self):
        stress_index = 0
        d = date.today()
        db = self.get_db()
        
        row = db.execute("SELECT stress_level from survey WHERE badge_no = ? and date = ?", (session['badge_no'], d)).fetchone()
        survey_stress = row['stress_level'] if row else 0

        row1 = db.execute("SELECT stress_level from journal WHERE badge_no = ? and date = ?", (session['badge_no'], d)).fetchone()
        journal_stress = row1['stress_level'] if row1 else 0

        row2 = db.execute("SELECT stress_level from wearables WHERE badge_no = ? and date = ?", (session['badge_no'], d)).fetchone()
        wearables_stress = row2['stress_level'] if row2 else 0

        row3 = db.execute("SELECT stress_level from  audio WHERE badge_no = ? and date = ?", (session['badge_no'], d)).fetchone()
        audio_stress = row3['stress_level'] if row3 else 0

        stress_index = (survey_stress/5)+(journal_stress*3)+(wearables_stress+1 if wearables_stress>0 else 0)+(audio_stress)
        existing = db.execute("SELECT * FROM final_stats WHERE badge_no = ? AND date = ?", (session['badge_no'], date.today().strftime('%Y-%m-%d'))).fetchone()
        if existing:
            db.execute("UPDATE final_stats SET stress_level = ? WHERE badge_no = ? AND date = ?", (stress_index, session['badge_no'], date.today().strftime('%Y-%m-%d')))
        else:
            db.execute("INSERT INTO final_stats VALUES(?, ?, ?)", (session['badge_no'], date.today().strftime('%Y-%m-%d'), stress_index))

        db.commit()

    def send_mail():
        recipient = "fahizfaheem538@gmail.com"
        sender = "bhushankulai2020@gmail.com"
        app_password = "xbhd lolz oxxr kjda"

        msg = EmailMessage()
        msg["Subject"] = "High stress levels of your officer"
        msg["From"] = sender
        msg["To"] = recipient
        msg.set_content(f"Your Officer {g.user['full_name']} Badge number {g.user['badge_no']} ranked as a {g.user['rank']} has been really stressed this week")

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(sender, app_password)
                smtp.send_message(msg)
                print("Otp sent to", recipient)
        except Exception as e:
                print("failed to send OTP", e)

app = Flask(__name__)
app.secret_key = 'top_secret'
b = backend(app)
b.init_db()

@app.before_request
def load_logged_in_user():
    badge_no = session.get('badge_no')
    if badge_no is None:
        g.user = None
    else:
        db = b.get_db()
        g.user = db.execute(
            'SELECT full_name, email, rank, badge_no FROM users WHERE badge_no = ?',
            (badge_no,)
        ).fetchone()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        return b.Login(email, password)
        
    return render_template('login.html')

@app.route('/register', methods=['POST', 'GET'])
def register():
    b.update_final()
    if request.method == 'POST':
        full_name = request.form['full_name']
        badge_number = request.form['badge_number']
        email = request.form['email']
        password = request.form['password']
        rank = request.form['rank']

        status = b.Register(full_name, badge_number, rank, email, password)
        
        if status == True:
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard', methods=['POST', 'GET'])
def dashboard():
    if g.user is None:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))
    b.update_final()
    rank = g.user['rank']
    name = g.user['full_name']
    time = date.today()
    stress_index = int(b.get_stress_index())
    if stress_index >= 8:
        #b.send_mail()
        pass
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekly_data = b.get_weekly_data()
    stress_average = b.get_stress_average()
    recommendations = b.get_recommendations()
    return render_template('dashboard.html', 
                           full_name=name, 
                           today_date=time,
                           rank=rank, 
                           stress_level=stress_index, 
                           chart_labels=labels,
                           chart_data = weekly_data,
                           stress_average = stress_average,
                           recommendations = recommendations,
                           mood = stress_average)

@app.route('/submit_interactive_status', methods=['POST'])
def submit_interactive_status():  
    pass

@app.route('/submit-survey', methods=['POST'])
def submit_survey():
    data = request.get_json()
    answers = data.get('answers', [])
    answers = [int(a) for a in answers]
    print("Received answers:", answers)
    stress_score = (answers[0]*2) + (answers[1]*2) + (answers[2]*2) + (answers[3]*2) + (answers[4]*2)
    if stress_score >= 8:
        flash("Highly Stressed")
    elif stress_score >= 6:
        flash("Moderately Stressed")
    else:
        flash("Not Stressed")
    b.update_survey(answers, stress_score)

    return jsonify({"success": True, "message": "Survey received!"})


@app.route('/journal', methods=['GET', 'POST'])
def journal():
    if g.user is None:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

    current_date_str = date.today().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        content = request.form.get('content')
        b.update_journal(content, current_date_str) 
        return redirect(url_for('journal'))

    b.update_final()
    rank = g.user['rank']
    name = g.user['full_name']
    time = date.today()
    stress_index = int(b.get_stress_index())
    
    entries = b.get_all_journal_entries() 

    today_content_row = b.get_db().execute(
        "SELECT data FROM journal WHERE badge_no = ? AND date = ?",
        (g.user['badge_no'], current_date_str) 
    ).fetchone()
    today_content = today_content_row['data'] if today_content_row else ''
    

    return render_template('journal.html',
                           full_name=name, 
                           today_date=time,
                           rank=rank, 
                           stress_level=stress_index,
                           entries=entries,
                           today_content=today_content)


@app.route('/survey')
def survey():
    if g.user is None:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))
    
    b.update_final()    
    name = g.user['full_name']
    time = date.today()
    stress_index = int(b.get_stress_index())
    rank = g.user['rank']
    return render_template('survey.html',
                           full_name = name,
                           today_date = time,
                           stress_level = stress_index,
                           rank = rank)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return render_template('login.html')

@app.route('/wearables')
def wearables():
    if g.user is None:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))
    
    b.update_final()
    name = g.user['full_name']
    time = date.today()
    stress_index = int(b.get_stress_index())
    rank = g.user['rank']
        
    return render_template('wearables.html', 
                           full_name = name,
                           today_date = time,
                           stress_level = stress_index,
                           rank = rank)

@app.route('/submit_wearables_data', methods=['POST'])
def submit_wearables_data():
    name = g.user['full_name']
    time = date.today()
    stress_index = int(b.get_stress_index())
    rank = g.user['rank']
    if request.method == 'POST':
        try:
            body_temp = float(request.form.get('body_temp'))
            blood_oxygen = float(request.form.get('blood_oxygen'))
            sleep = float(request.form.get('hours_sleep'))
            heart_rate = float(request.form.get('heart_rate'))

            b.update_wearables(body_temp, blood_oxygen, sleep, heart_rate)
        except:
            flash("Error")

    return render_template('wearables.html', full_name = name,
                           today_date = time,
                           stress_level = stress_index,
                           rank = rank)

@app.route('/audio')
def audio():
    if g.user is None:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))
    
    name = g.user['full_name']
    time = date.today()
    stress_index = int(b.get_stress_index())
    rank = g.user['rank']
        
    return render_template('audio.html',full_name = name,
                           today_date = time,
                           stress_level = stress_index,
                           rank = rank
                           )

if __name__ == '__main__':
    app.run(debug=True)