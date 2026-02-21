from flask import Flask, request, jsonify, send_from_directory
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import json
from datetime import datetime

app = Flask(__name__, static_folder='.')

# Config — set these as environment variables on the Pi
GMAIL_USER = os.environ.get('GMAIL_USER', 'amacd86@gmail.com')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
NOTIFY_EMAIL = os.environ.get('NOTIFY_EMAIL', 'amacd86@gmail.com')
RSVP_LOG = '/home/gus/wedding/rsvps.json'

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

    # Serve static files
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

@app.route('/rsvp', methods=['POST'])
def rsvp():
    data = request.get_json()

    first = data.get('firstName', '')
    last = data.get('lastName', '')
    email = data.get('email', '')
    attending = data.get('attending', '')
    guests = data.get('guests', '1')
    dietary = data.get('dietary', 'None')
    message = data.get('message', '')

    # Log RSVP to file
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

    # Send email notification
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