from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import json
from datetime import datetime, timedelta
import csv
from io import StringIO
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

app = Flask(__name__, static_folder='.')
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key-on-pi')

# Config
GMAIL_USER = os.environ.get('GMAIL_USER', 'amacd86@gmail.com')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
NOTIFY_EMAIL = os.environ.get('NOTIFY_EMAIL', 'amacd86@gmail.com')
RSVP_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rsvps.json')
SITE_PASSWORD = os.environ.get('SITE_PASSWORD', 'woodstock2026')
RSVP_ADMIN_PASSWORD = os.environ.get('RSVP_ADMIN_PASSWORD', 'change-me')

# Scheduler for Friday digest
scheduler = BackgroundScheduler()
scheduler.start()

def is_logged_in():
    return session.get('authenticated') == True

def send_email(to_email, subject, body):
    """Helper to send email"""
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f'Failed to send email to {to_email}: {e}')
        return False

def get_all_rsvps():
    """Load all RSVPs from JSON"""
    try:
        if os.path.exists(RSVP_LOG):
            with open(RSVP_LOG, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f'Failed to load RSVPs: {e}')
    return []

def send_weekly_digest():
    """Send digest of RSVPs from the past week"""
    rsvps = get_all_rsvps()
    if not rsvps:
        return
    
    # Get RSVPs from past 7 days
    now = datetime.now()
    week_ago = (now - timedelta(days=7)).isoformat()
    recent = [r for r in rsvps if r.get('timestamp', '') > week_ago]
    
    if not recent:
        return
    
    # Build digest
    subject = f'Wedding RSVP Weekly Digest — {len(recent)} new responses'
    body = f"Weekly RSVP Digest\n{'='*50}\n\n"
    body += f"Period: Last 7 days\nTotal RSVPs: {len(recent)}\n\n"
    
    yes_count = sum(1 for r in recent if r.get('attending') == 'yes')
    no_count = len(recent) - yes_count
    body += f"Attending: {yes_count}\nDeclined: {no_count}\n\n"
    
    body += "Responses:\n" + "-"*50 + "\n\n"
    
    for r in recent:
        body += f"Name: {r.get('name', 'N/A')}\n"
        body += f"Email: {r.get('email', 'N/A')}\n"
        body += f"Attending: {r.get('attending', 'N/A')}\n"
        body += f"Thursday: {r.get('thursday', 'N/A')}\n"
        body += f"Dietary: {r.get('dietary', 'None')}\n"
        body += f"Song Request: {r.get('song_request', 'None')}\n"
        body += f"Notes: {r.get('message', 'None')}\n"
        body += f"Submitted: {r.get('timestamp', 'N/A')}\n"
        body += "-"*50 + "\n\n"
    
    send_email(NOTIFY_EMAIL, subject, body)

# Schedule digest for Friday 9:30am EST
scheduler.add_job(
    send_weekly_digest,
    'cron',
    day_of_week='fri',
    hour=9,
    minute=30,
    timezone='US/Eastern'
)

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
    thursday = data.get('thursday', 'no')
    dietary = data.get('dietary', 'None')
    song_request = data.get('songRequest', 'None')
    message = data.get('message', '')

    rsvp_entry = {
        'timestamp': datetime.now().isoformat(),
        'name': f'{first} {last}',
        'email': email,
        'attending': attending,
        'thursday': thursday,
        'dietary': dietary,
        'song_request': song_request,
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

    # Send celebratory confirmation email to guest
    attending_text = 'Joyfully accepting! 🎉' if attending == 'yes' else 'Regretfully declining'
    thursday_text = 'Yes' if thursday == 'yes' else 'No'
    
    guest_body = f"""
Hi {first},

Thank you for RSVPing to our wedding! Here's what we have on file:

Name: {first} {last}
Attending: {attending_text}
Joining us Thursday night: {thursday_text}
Dietary Restrictions: {dietary if dietary != 'None' else 'None'}
Song Request: {song_request if song_request != 'None' else 'None'}

We can't wait to celebrate with you!

— Angus & Tessa
    """.strip()
    
    send_email(email, 'Wedding RSVP Confirmation ✓', guest_body)

    # Send notification to Angus
    attending_str = 'Joyfully accepts ✓' if attending == 'yes' else 'Regretfully declines'
    angus_body = f"""
New RSVP from {first} {last}

Attending: {attending_str}
Thursday Night: {thursday_text}
Email: {email}
Dietary: {dietary}
Song Request: {song_request}

Message:
{message if message else '(No message)'}

— Sent from GusPi Wedding Site
    """.strip()

    send_email(NOTIFY_EMAIL, f'Wedding RSVP: {first} {last} — {attending_str}', angus_body)

    return jsonify({'status': 'ok'}), 200


# --- RSVP Admin ---
@app.route('/rsvps-admin', methods=['GET', 'POST'])
def rsvps_admin():
    if request.method == 'POST':
        # Login
        if request.form.get('password') == RSVP_ADMIN_PASSWORD:
            session['rsvp_admin'] = True
            return redirect('/rsvps-admin')
        else:
            return render_template_string(ADMIN_LOGIN_TEMPLATE, error=True)
    
    # Check if logged in
    if not session.get('rsvp_admin'):
        return render_template_string(ADMIN_LOGIN_TEMPLATE, error=False)
    
    # Show RSVPs
    rsvps = get_all_rsvps()
    return render_template_string(ADMIN_DASHBOARD_TEMPLATE, rsvps=rsvps, count=len(rsvps))

@app.route('/rsvps-admin/logout')
def rsvps_admin_logout():
    session.pop('rsvp_admin', None)
    return redirect('/rsvps-admin')

@app.route('/rsvps-admin/download')
def rsvps_download():
    if not session.get('rsvp_admin'):
        return redirect('/rsvps-admin')
    
    rsvps = get_all_rsvps()
    
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=['timestamp', 'name', 'email', 'attending', 'thursday', 'dietary', 'song_request', 'message'])
    writer.writeheader()
    writer.writerows(rsvps)
    
    csv_data = output.getvalue()
    
    return csv_data, 200, {
        'Content-Disposition': f'attachment; filename="wedding_rsvps_{datetime.now().strftime("%Y%m%d")}.csv"',
        'Content-Type': 'text/csv'
    }


# HTML Templates
ADMIN_LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>RSVP Admin Login</title>
    <style>
        body { font-family: Arial; background: #f5ede0; margin: 0; padding: 20px; }
        .container { max-width: 400px; margin: 100px auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #5c1f4a; margin-top: 0; }
        input { width: 100%; padding: 10px; margin: 10px 0 20px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { width: 100%; padding: 10px; background: #5c1f4a; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #3a9e8f; }
        .error { color: red; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>RSVP Admin</h1>
        {% if error %}<div class="error">Incorrect password</div>{% endif %}
        <form method="post">
            <input type="password" name="password" placeholder="Admin Password" required autofocus>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>
"""

ADMIN_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>RSVP Admin Dashboard</title>
    <style>
        body { font-family: Arial; background: #f5ede0; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        h1 { color: #5c1f4a; margin: 0; }
        .logout { color: #5c1f4a; text-decoration: none; }
        .logout:hover { text-decoration: underline; }
        .stats { background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .stat { display: inline-block; margin-right: 30px; }
        .stat-number { font-size: 24px; font-weight: bold; color: #5c1f4a; }
        .stat-label { color: #666; font-size: 14px; }
        table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; }
        th { background: #5c1f4a; color: white; padding: 12px; text-align: left; }
        td { padding: 12px; border-bottom: 1px solid #eee; }
        tr:hover { background: #f9f9f9; }
        .btn { display: inline-block; padding: 10px 20px; background: #3a9e8f; color: white; text-decoration: none; border-radius: 4px; margin-bottom: 20px; }
        .btn:hover { background: #5c1f4a; }
        .yes { color: green; font-weight: bold; }
        .no { color: red; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>RSVP Dashboard</h1>
            <a href="/rsvps-admin/logout" class="logout">Logout</a>
        </div>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-number">{{ count }}</div>
                <div class="stat-label">Total RSVPs</div>
            </div>
            <div class="stat">
                <div class="stat-number">{{ rsvps|selectattr('attending', 'equalto', 'yes')|list|length }}</div>
                <div class="stat-label">Attending</div>
            </div>
            <div class="stat">
                <div class="stat-number">{{ rsvps|selectattr('thursday', 'equalto', 'yes')|list|length }}</div>
                <div class="stat-label">Thursday Night</div>
            </div>
        </div>
        
        <a href="/rsvps-admin/download" class="btn">Download as CSV</a>
        
        <table>
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Attending</th>
                    <th>Thursday</th>
                    <th>Dietary</th>
                    <th>Song Request</th>
                    <th>Message</th>
                    <th>Submitted</th>
                </tr>
            </thead>
            <tbody>
                {% for rsvp in rsvps|reverse %}
                <tr>
                    <td>{{ rsvp.name }}</td>
                    <td>{{ rsvp.email }}</td>
                    <td><span class="{% if rsvp.attending == 'yes' %}yes{% else %}no{% endif %}">{{ rsvp.attending|upper }}</span></td>
                    <td>{{ rsvp.thursday|upper }}</td>
                    <td>{{ rsvp.dietary }}</td>
                    <td>{{ rsvp.song_request }}</td>
                    <td>{{ rsvp.message }}</td>
                    <td>{{ rsvp.timestamp|truncate(10, True, '') }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""


# --- Photo Gallery Upload/Serve ---
PHOTOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wedding_photos_PRE')
os.makedirs(PHOTOS_DIR, exist_ok=True)

@app.route('/photos-list')
def photos_list():
    if not is_logged_in():
        return jsonify({'status': 'unauthorized'}), 401
    try:
        files = [f for f in os.listdir(PHOTOS_DIR)
                 if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))]
        files.sort(reverse=True)
        return jsonify({'photos': files})
    except Exception as e:
        return jsonify({'photos': []})

@app.route('/upload', methods=['POST'])
def upload():
    if not is_logged_in():
        return jsonify({'status': 'unauthorized'}), 401
    file = request.files.get('photo')
    if not file:
        return jsonify({'status': 'error', 'message': 'No file'}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        return jsonify({'status': 'error', 'message': 'Invalid file type'}), 400
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = f'{timestamp}{ext}'
    file.save(os.path.join(PHOTOS_DIR, filename))
    return jsonify({'status': 'ok', 'filename': filename})

@app.route('/photos/<filename>')
def serve_photo(filename):
    if not is_logged_in():
        return jsonify({'status': 'unauthorized'}), 401
    return send_from_directory(PHOTOS_DIR, filename)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=False)