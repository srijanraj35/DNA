import sqlite3
import os

# Correct the database path to match app.py
db_path = "static/wellness.db"

# Make sure the static folder exists
os.makedirs("static", exist_ok=True)

# Connect to DB
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Drop old tables if they exist (optional cleanup)
c.execute("DROP TABLE IF EXISTS users;")
c.execute("DROP TABLE IF EXISTS stress_logs;")

# Update users table schema to match app.py's requirements
c.execute('''
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    badge TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role TEXT DEFAULT 'officer',
    stress_level REAL DEFAULT 50.0
)
''')

# Create stress_logs table
c.execute('''
CREATE TABLE stress_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    mood TEXT,
    stress_score REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
''')

print("✅ Database initialized successfully!")

conn.commit()
conn.close()