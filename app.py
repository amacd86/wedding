from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import json
from datetime import datetime

app = Flask(__name__, static_folder='.')
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key-on-pi')

# Config
GMAIL_USER = os.environ.get('GMAIL_USER', 'amacd86@gmail.com')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
NOTIFY_EMAIL = os.environ.get('NOTIFY_EMAIL', 'amacd86@gmail.com')
RSVP_LOG = '/home/gus/wedding/rsvps.json'
SITE_PASSWORD = os.environ.get('SITE_PASSWORD', 'woodstock2026')

def is_logged_in():
    return session.get('authenticated') == True

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = False
    if request.method == 'POST':
        if request.form.get('password') == SITE_PASSWORD:
            session['authenticated'] = True
            return redirect('/')
        else:
            error = True
    return send_from_directory('.', 'login.html'), (401 if error else 200)

@app.route('/login-check', methods=['POST'])
def login_check():
    data = request.get_json()
    if data.get('password') == SITE_PASSWORD:
        session['authenticated'] = True
        return jsonify({'status': 'ok'}), 200
    return jsonify({'status': 'error'}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/')
def index():
    if not is_logged_in():
        return redirect('/login')
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    if filename in ('login.html', 'save-the-date.jpg', 'favicon.ico'):
        return send_from_directory('.', filename)
    if not is_logged_in():
        return redirect('/login')
    return send_from_directory('.', filename)

@app.route('/rsvp', methods=['POST'])
def rsvp():
    if not is_logged_in():
        return jsonify({'status': 'unauthorized'}), 401

    data = request.get_json()
    first = data.get('firstName', '')
    last = data.get('lastName', '')
    email = data.get('email', '')
    attending = data.get('attending', '')
    guests = data.get('guests', '1')
    dietary = data.get('dietary', 'None')
    message = data.get('message', '')

    rsvp_entry = {
        'timestamp': datetime.now().isoformat(),
        'name': f'{first} {last}',
        'email': email,
        'attending': attending,
        'guests': guests,
        'dietary': dietary,
        'message': message
    }

    try:
        if os.path.exists(RSVP_LOG):
            with open(RSVP_LOG, 'r') as f:
                rsvps = json.load(f)
        else:
            rsvps = []
        rsvps.append(rsvp_entry)
        with open(RSVP_LOG, 'w') as f:
            json.dump(rsvps, f, indent=2)
    except Exception as e:
        print(f'Failed to log RSVP: {e}')

    try:
        attending_str = 'Joyfully accepts ✓' if attending == 'yes' else 'Regretfully declines'
        body = f"""
New RSVP from {first} {last}

Attending: {attending_str}
Guests: {guests}
Email: {email}
Dietary: {dietary}

Message:
{message}

— Sent from GusPi Wedding Site
        """.strip()

        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = NOTIFY_EMAIL
        msg['Subject'] = f'Wedding RSVP: {first} {last} — {attending_str}'
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f'Failed to send email: {e}')

    return jsonify({'status': 'ok'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=False)