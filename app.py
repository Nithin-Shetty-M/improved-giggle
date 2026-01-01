# ADMIN-BASED EMAIL BIRTHDAY WISHER WITH OTP SIGNUP (FINAL VERSION)

from flask import Flask, render_template, request, redirect, session, jsonify, url_for
import sqlite3, os, hashlib, random, smtplib, re
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

app = Flask(__name__)
app.secret_key = 'super-secret-key'

# ---------------- CONFIG ----------------
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SENDER_EMAIL = 'dailybirthdaywisher@gmail.com'        # ADMIN EMAIL (FILL AT RUNTIME / ENV)
SENDER_APP_PASSWORD = 'bici dlqj otsu dvor' # ADMIN APP PASSWORD (FILL AT RUNTIME / ENV)

USERS_DB = 'users.db'
DATA_DIR = 'data'
os.makedirs(DATA_DIR, exist_ok=True)
OTP_STORE = {}

# ---------------- HELPERS ----------------
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def valid_email(email):
    return re.match(r'^[^@]+@[^@]+\.[^@]+$', email)

# ---------------- OTP EMAIL ----------------
def send_otp(email, otp):
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = email
    msg['Subject'] = 'OTP Verification – Birthday Mailer'
    msg.attach(MIMEText(f'Your OTP is {otp}. It is valid for 5 minutes.', 'plain'))

    server.send_message(msg)
    server.quit()

# ---------------- INIT USERS DB ----------------
with sqlite3.connect(USERS_DB) as con:
    con.execute('''CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )''')

# ---------------- LOGIN ----------------
@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        password = hash_password(request.form.get('password',''))

        with sqlite3.connect(USERS_DB) as con:
            u = con.execute(
                'SELECT * FROM users WHERE email=? AND password=?',
                (email, password)
            ).fetchone()

        if not u:
            return render_template('login.html',
                error='Invalid email or password')

        session['uid'] = u[0]
        session['name'] = u[1]
        session['email'] = u[2]

        return redirect(url_for('dashboard'))

    return render_template('login.html')



# ---------------- SIGNUP ----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':

        action = request.form.get('action')

        # STEP 1 → SEND OTP
        if action == 'send_otp':
            email = request.form.get('email','').strip()
            password = request.form.get('password','')
            confirm = request.form.get('confirm','')

            if not valid_email(email):
                return render_template('signup.html', error='Invalid email format')

            if len(password) < 8 or len(password) > 16:
                return render_template('signup.html', error='Password must be 8–16 characters')

            if password != confirm:
                return render_template('signup.html', error='Passwords do not match')

            # Check if user already exists
            with sqlite3.connect(USERS_DB) as con:
                exists = con.execute(
                    'SELECT 1 FROM users WHERE email=?', (email,)
                ).fetchone()

            if exists:
                return render_template('signup.html', error='Email already registered')

            otp = random.randint(100000,999999)
            OTP_STORE[email] = otp
            send_otp(email, otp)

            session['pending_user'] = {
                'email': email,
                'password': hash_password(password)
            }

            return render_template('signup.html', otp_sent=True, email=email)

        # STEP 2 → VERIFY OTP & CREATE USER
        if action == 'verify_otp':
            otp = request.form.get('otp','').strip()
            pending = session.get('pending_user')

            if not pending:
                return redirect(url_for('signup'))

            if str(OTP_STORE.get(pending['email'])) != otp:
                return render_template(
                    'signup.html',
                    error='Incorrect OTP',
                    otp_sent=True,
                    email=pending['email']
                )

            with sqlite3.connect(USERS_DB) as con:
                con.execute(
                    'INSERT INTO users(name,email,password) VALUES(?,?,?)',
                    (None, pending['email'], pending['password'])
                )

            OTP_STORE.pop(pending['email'], None)
            session.pop('pending_user')

            return redirect(url_for('login'))

    return render_template('signup.html')



'''# ---------------- VERIFY OTP ----------------
@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    otp = request.form.get('otp','').strip()
    pending = session.get('pending_user')

    if not pending:
        return redirect(url_for('signup'))

    if str(OTP_STORE.get(pending['email'])) != otp:
        return render_template(
            'verify_otp.html',
            error='Invalid OTP',
            email=pending['email']
        )

    with sqlite3.connect(USERS_DB) as con:
        con.execute(
            'INSERT INTO users(name,email,password) VALUES(?,?,?)',
            (None, pending['email'], pending['password'])
        )

    OTP_STORE.pop(pending['email'], None)
    session.pop('pending_user')

    return redirect(url_for('login'))'''


# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'uid' not in session:
        return redirect(url_for('login'))

    db = f"{DATA_DIR}/user_{session['uid']}.db"
    with sqlite3.connect(db) as con:
        con.execute('''CREATE TABLE IF NOT EXISTS birthdays(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,email TEXT,day INT,month INT,gender TEXT
        )''')
        rows = con.execute('SELECT * FROM birthdays').fetchall()

    return render_template('index.html', birthdays=rows)

# ---------------- ADD BIRTHDAY ----------------
@app.route('/add', methods=['POST'])
def add():
    db = f"{DATA_DIR}/user_{session['uid']}.db"
    with sqlite3.connect(db) as con:
        con.execute('INSERT INTO birthdays VALUES(NULL,?,?,?,?,?)', tuple(request.form.values()))
    return redirect(url_for('dashboard'))

# ---------------- ADD NAME ----------------
@app.route('/update_name', methods=['POST'])
def update_name():
    if 'uid' not in session:
        return redirect(url_for('login'))

    name = request.form.get('name','').strip()

    if len(name) < 2 or not re.match(r'^[A-Za-z ]+$', name):
        return redirect(url_for('dashboard'))

    with sqlite3.connect(USERS_DB) as con:
        con.execute('UPDATE users SET name=? WHERE id=?',
                    (name, session['uid']))

    session['name'] = name
    return redirect(url_for('dashboard'))


# ---------------- TODAY ----------------
@app.route('/today')
def today():
    now = datetime.now()
    db = f"{DATA_DIR}/user_{session['uid']}.db"
    with sqlite3.connect(db) as con:
        rows = con.execute('SELECT * FROM birthdays WHERE day=? AND month=?',(now.day,now.month)).fetchall()
    return render_template('today.html', birthdays=rows)

# ---------------- DELETE BIRTHDAY ----------------
@app.route('/delete/<int:id>')
def delete(id):
    if 'uid' not in session:
        return redirect(url_for('login'))

    db = f"{DATA_DIR}/user_{session['uid']}.db"

    with sqlite3.connect(db) as con:
        con.execute('DELETE FROM birthdays WHERE id=?', (id,))
        con.commit()

    return redirect(url_for('dashboard'))


# ---------------- SEND EMAIL (ADMIN MAIL) ----------------
@app.route('/send', methods=['POST'])
def send():
    if 'uid' not in session:
        return jsonify({'status': 'unauthorized'}), 401
    selected = request.json.get('selected', [])
    if not selected:
        return jsonify({'status':'no_birthdays'})

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)

    for p in selected:
        msg = MIMEMultipart('alternative')
        msg['From'] = SENDER_EMAIL
        msg['To'] = p['email']
        msg['Subject'] = 'Happy Birthday 🎉'

        html = f"""
        <html><body style='font-family:Arial'>
        <h2>🎂 Happy Birthday {p['name']}!</h2>
        <p style='margin-top:15px;'>Warm wishes from <b>{session.get('name')}</b> 💐</p></h2>
        <p>Wishing you a wonderful year ahead.</p>
        </body></html>
        """
        msg.attach(MIMEText(html,'html'))
        server.send_message(msg)

    server.quit()
    return jsonify({'status':'sent'})

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# if __name__ == '__main__':
#     app.run(debug=True)

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
