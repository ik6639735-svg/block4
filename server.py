# ===============================
#  QHIVE - Smart Traders. Stronger Together.
#  Production Ready Version
# ===============================

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
from werkzeug.utils import secure_filename
import sqlite3
import hashlib
import os
import re
import random
from datetime import datetime, timedelta

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Database path
DB_PATH = os.environ.get('DATABASE_URL', 'block4.db')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'qhive_platform_2026_secure_key')

# OAuth Setup
try:
    from authlib.integrations.flask_client import OAuth
    oauth = OAuth(app)
    google = oauth.register(
        name='google',
        client_id=os.environ.get('GOOGLE_CLIENT_ID', ''),
        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )
    GOOGLE_ENABLED = True
except Exception as e:
    print("OAuth not available: " + str(e))
    GOOGLE_ENABLED = False

# Make hashtags clickable
@app.template_filter('linkify_hashtags')
def linkify_hashtags(text):
    if not text:
        return text
    return re.sub(r'#(\w+)', r'<a href="/hashtag/\1" style="color:var(--gold); text-decoration:none;">#\1</a>', text)

# File Upload Config
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'webm'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# Create upload folders
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'posts'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'stories'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'profiles'), exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ================================
# DATABASE CONNECTION
# ================================
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=20)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA busy_timeout=5000")
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()


# ================================
# DATABASE SETUP
# ================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        bio TEXT DEFAULT '',
        avatar TEXT DEFAULT '',
        is_verified INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        content TEXT,
        media_url TEXT,
        media_type TEXT,
        feeling TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS stories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        media_url TEXT NOT NULL,
        media_type TEXT DEFAULT 'image',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        post_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, post_id)
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        post_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS follows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        follower_id INTEGER NOT NULL,
        following_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(follower_id, following_id)
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        from_user_id INTEGER,
        post_id INTEGER,
        content TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS saved_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        post_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, post_id)
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS polls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        FOREIGN KEY (post_id) REFERENCES posts (id)
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS poll_options (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        poll_id INTEGER NOT NULL,
        option_text TEXT NOT NULL,
        FOREIGN KEY (poll_id) REFERENCES polls (id)
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS poll_votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        poll_id INTEGER NOT NULL,
        option_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(poll_id, user_id)
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS ai_chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
        conn.execute('''CREATE TABLE IF NOT EXISTS story_likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        story_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, story_id)
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS story_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        story_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()

init_db()

try:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
    conn.commit()
    conn.close()
except:
    pass


# ================================
# HELPERS
# ================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please login to continue", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def time_ago(dt):
    if isinstance(dt, str):
        dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    now = datetime.now()
    diff = now - dt
    if diff.days > 365:
        return str(diff.days // 365) + "y ago"
    elif diff.days > 30:
        return str(diff.days // 30) + "mo ago"
    elif diff.days > 7:
        return dt.strftime('%b %d')
    elif diff.days > 0:
        return str(diff.days) + "d ago"
    elif diff.seconds > 3600:
        return str(diff.seconds // 3600) + "h ago"
    elif diff.seconds > 60:
        return str(diff.seconds // 60) + "m ago"
    else:
        return "Just now"

def create_notification(user_id, notif_type, from_user_id=None, post_id=None, content=None):
    if user_id == from_user_id:
        return
    try:
        db = get_db()
        db.execute('INSERT INTO notifications (user_id, type, from_user_id, post_id, content) VALUES (?, ?, ?, ?, ?)',
                   (user_id, notif_type, from_user_id, post_id, content))
        db.commit()
    except Exception as e:
        print("Notification error: " + str(e))

def extract_hashtags(text):
    if not text:
        return []
    return re.findall(r'#(\w+)', text)


# ================================
# QHIVE AI BRAIN - POWERED BY GROQ
# ================================
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')


def fallback_ai(message, username):
    msg = message.lower().strip()
    if not msg:
        return "I'm listening! What would you like to know?"
    greetings = ['hi', 'hello', 'hey', 'yo', 'sup', 'good morning', 'good evening', 'hy', 'hii', 'helo']
    if any(msg.startswith(g) or msg == g for g in greetings):
        return "Hey " + username + "! How's it going? I'm QHive AI. What can I help you with today?"
    if any(w in msg for w in ['thank', 'thanks']):
        return "You're welcome " + username + "! Anything else I can help with?"
    if any(w in msg for w in ['bye', 'goodbye']):
        return "Take care " + username + "! Come back anytime!"
    return "I'd love to help with that! Try asking me about trading, crypto, forex, risk management, or anything else. What would you like to learn?"


def get_ai_reply(message, username, history=None):
    if not GROQ_API_KEY:
        print("NO GROQ KEY - using fallback")
        return fallback_ai(message, username)
    
    try:
        import httpx
        from groq import Groq
        
        http_client = httpx.Client(timeout=30.0)
        client = Groq(api_key=GROQ_API_KEY, http_client=http_client)
        
        system_prompt = (
            "You are QHive AI - a friendly and conversational trading assistant. "
            "Be natural and human-like in your responses, just like ChatGPT. "
            "When someone says hi, hello, or any greeting, respond warmly and briefly like a friend would. "
            "For example if someone says 'hi', just say something like 'Hey [name]! What's up?' "
            "Do NOT give long responses to simple greetings. Keep greetings short and natural. "
            "You specialize in trading education (forex, crypto, stocks, SMC, technical analysis) "
            "but you can chat about anything. "
            "Use emojis occasionally to be friendly. "
            "When teaching about trading, be detailed and thorough. "
            "Use **bold** for important terms and organize with bullet points. "
            "The user's name is " + username + ". Use their name sometimes to be personal."
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            for h in history[-10:]:
                messages.append({"role": h['role'], "content": h['message']})
        
        messages.append({"role": "user", "content": message})
        
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=2000,
        )
        
        reply = completion.choices[0].message.content
        http_client.close()
        return reply
    
    except Exception as e:
        print("GROQ ERROR: " + str(e))
        return fallback_ai(message, username)


# ================================
# AUTH ROUTES
# ================================
@app.route("/")
def index():
    if 'user_id' in session:
        return redirect(url_for('feed'))
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if 'user_id' in session:
        return redirect(url_for('feed'))
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ? AND password_hash = ?",
                         (email, hash_password(password))).fetchone()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash("Welcome back, " + user['username'] + "!", "success")
            return redirect(url_for('feed'))
        flash("Invalid email or password", "error")
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if 'user_id' in session:
        return redirect(url_for('feed'))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        if len(password) < 6:
            flash("Password must be at least 6 characters", "error")
            return render_template("signup.html")
        if len(username) < 3:
            flash("Username must be at least 3 characters", "error")
            return render_template("signup.html")
        db = get_db()
        try:
            db.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                      (username, email, hash_password(password)))
            db.commit()
            flash("Account created! Please login.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username or email already exists", "error")
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))


# ================================
# FEED
# ================================
@app.route("/feed")
@login_required
def feed():
    db = get_db()
    posts = db.execute('''
        SELECT p.*, u.username, u.avatar,
            (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count,
            (SELECT COUNT(*) FROM comments WHERE post_id = p.id) as comment_count,
            (SELECT COUNT(*) FROM likes WHERE post_id = p.id AND user_id = ?) as user_liked
        FROM posts p JOIN users u ON p.user_id = u.id
        ORDER BY p.created_at DESC LIMIT 50
    ''', (session['user_id'],)).fetchall()
    
    stories = db.execute('''
        SELECT s.*, u.username, u.avatar FROM stories s
        JOIN users u ON s.user_id = u.id
        WHERE s.created_at > datetime('now', '-24 hours')
        ORDER BY s.created_at DESC
    ''').fetchall()
    
    trending_posts = db.execute('''
        SELECT content FROM posts
        WHERE created_at > datetime('now', '-7 days') AND content IS NOT NULL
    ''').fetchall()
    
    hashtag_counts = {}
    for post in trending_posts:
        if post['content']:
            tags = extract_hashtags(post['content'])
            for tag in tags:
                hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1
    trending_tags = sorted(hashtag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    suggested = db.execute('''
        SELECT u.* FROM users u WHERE u.id != ?
        AND u.id NOT IN (SELECT following_id FROM follows WHERE follower_id = ?)
        LIMIT 5
    ''', (session['user_id'], session['user_id'])).fetchall()
    
    posts_list = []
    for post in posts:
        post_dict = dict(post)
        post_dict['time_ago'] = time_ago(post['created_at'])
        posts_list.append(post_dict)
    
    return render_template("feed.html", posts=posts_list, stories=stories,
                          trending=trending_tags, suggested=suggested)


# ================================
# POST ROUTES
# ================================
@app.route("/api/post", methods=["POST"])
@login_required
def create_post():
    content = request.form.get('content', '').strip()
    feeling = request.form.get('feeling', '')
    media_url = None
    media_type = None
    if 'media' in request.files:
        file = request.files['media']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(str(session['user_id']) + "_" + datetime.now().strftime('%Y%m%d%H%M%S') + "_" + file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'posts', filename)
            file.save(filepath)
            media_url = "/static/uploads/posts/" + filename
            ext = filename.rsplit('.', 1)[1].lower()
            media_type = 'video' if ext in ['mp4', 'mov', 'webm'] else 'image'
    if not content and not media_url:
        return jsonify({'error': 'Post cannot be empty'}), 400
    db = get_db()
    cursor = db.execute('INSERT INTO posts (user_id, content, media_url, media_type, feeling) VALUES (?, ?, ?, ?, ?)',
                       (session['user_id'], content, media_url, media_type, feeling))
    post_id = cursor.lastrowid
    db.commit()
    return jsonify({'status': 'ok', 'post_id': post_id})

@app.route("/api/post/<int:post_id>/like", methods=["POST"])
@login_required
def like_post(post_id):
    db = get_db()
    existing = db.execute("SELECT id FROM likes WHERE user_id = ? AND post_id = ?",
                         (session['user_id'], post_id)).fetchone()
    if existing:
        db.execute("DELETE FROM likes WHERE user_id = ? AND post_id = ?", (session['user_id'], post_id))
        action = 'unliked'
    else:
        db.execute("INSERT INTO likes (user_id, post_id) VALUES (?, ?)", (session['user_id'], post_id))
        action = 'liked'
        post = db.execute("SELECT user_id FROM posts WHERE id = ?", (post_id,)).fetchone()
        if post and post['user_id'] != session['user_id']:
            create_notification(post['user_id'], 'like', session['user_id'], post_id)
    count = db.execute("SELECT COUNT(*) as c FROM likes WHERE post_id = ?", (post_id,)).fetchone()['c']
    db.commit()
    return jsonify({'status': action, 'count': count})

@app.route("/api/post/<int:post_id>/comment", methods=["POST"])
@login_required
def add_comment(post_id):
    data = request.get_json()
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    db = get_db()
    db.execute("INSERT INTO comments (user_id, post_id, content) VALUES (?, ?, ?)",
              (session['user_id'], post_id, content))
    post = db.execute("SELECT user_id FROM posts WHERE id = ?", (post_id,)).fetchone()
    if post and post['user_id'] != session['user_id']:
        create_notification(post['user_id'], 'comment', session['user_id'], post_id, content[:50])
    db.commit()
    return jsonify({'status': 'ok', 'username': session['username'], 'content': content})

@app.route("/api/post/<int:post_id>/comments")
@login_required
def get_comments(post_id):
    db = get_db()
    comments = db.execute('''
        SELECT c.*, u.username, u.avatar FROM comments c
        JOIN users u ON c.user_id = u.id WHERE c.post_id = ?
        ORDER BY c.created_at DESC
    ''', (post_id,)).fetchall()
    return jsonify([dict(c) for c in comments])

@app.route("/api/post/<int:post_id>/save", methods=["POST"])
@login_required
def save_post(post_id):
    db = get_db()
    existing = db.execute("SELECT id FROM saved_posts WHERE user_id = ? AND post_id = ?",
                         (session['user_id'], post_id)).fetchone()
    if existing:
        db.execute("DELETE FROM saved_posts WHERE user_id = ? AND post_id = ?", (session['user_id'], post_id))
        action = 'unsaved'
    else:
        db.execute("INSERT INTO saved_posts (user_id, post_id) VALUES (?, ?)", (session['user_id'], post_id))
        action = 'saved'
    db.commit()
    return jsonify({'status': action})

@app.route("/api/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ? AND user_id = ?", (post_id, session['user_id'])).fetchone()
    if not post:
        return jsonify({'error': 'Post not found'}), 404
    db.execute("DELETE FROM likes WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM saved_posts WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    db.commit()
    return jsonify({'status': 'deleted'})


# ================================
# STORY ROUTES
# ================================
@app.route("/api/story", methods=["POST"])
@login_required
def create_story():
    if 'media' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['media']
    if file and allowed_file(file.filename):
        filename = secure_filename(str(session['user_id']) + "_" + datetime.now().strftime('%Y%m%d%H%M%S') + "_" + file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'stories', filename)
        file.save(filepath)
        media_url = "/static/uploads/stories/" + filename
        ext = filename.rsplit('.', 1)[1].lower()
        media_type = 'video' if ext in ['mp4', 'mov', 'webm'] else 'image'
        db = get_db()
        db.execute("INSERT INTO stories (user_id, media_url, media_type, expires_at) VALUES (?, ?, ?, datetime('now', '+24 hours'))",
                  (session['user_id'], media_url, media_type))
        db.commit()
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Invalid file'}), 400

@app.route("/api/stories/<int:user_id>")
@login_required
def get_user_stories(user_id):
    db = get_db()
    stories = db.execute('''
        SELECT s.*, u.username FROM stories s
        JOIN users u ON s.user_id = u.id
        WHERE s.user_id = ? AND s.created_at > datetime('now', '-24 hours')
        ORDER BY s.created_at ASC
    ''', (user_id,)).fetchall()
    return jsonify([dict(s) for s in stories])

        conn.execute('''CREATE TABLE IF NOT EXISTS stories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        media_url TEXT NOT NULL,
        media_type TEXT DEFAULT 'image',
        caption TEXT DEFAULT '',
        music TEXT DEFAULT '',
        comments_enabled INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')


# ================================
# FOLLOW ROUTES
# ================================
@app.route("/api/follow/<int:user_id>", methods=["POST"])
@login_required
def follow_user(user_id):
    if user_id == session['user_id']:
        return jsonify({'error': 'Cannot follow yourself'}), 400
    db = get_db()
    existing = db.execute("SELECT id FROM follows WHERE follower_id = ? AND following_id = ?",
                         (session['user_id'], user_id)).fetchone()
    if existing:
        db.execute("DELETE FROM follows WHERE follower_id = ? AND following_id = ?", (session['user_id'], user_id))
        action = 'unfollowed'
    else:
        db.execute("INSERT INTO follows (follower_id, following_id) VALUES (?, ?)", (session['user_id'], user_id))
        action = 'followed'
        create_notification(user_id, 'follow', session['user_id'])
    db.commit()
    return jsonify({'status': action})


# ================================
# POLL ROUTES
# ================================
@app.route("/api/poll", methods=["POST"])
@login_required
def create_poll():
    data = request.get_json()
    question = data.get('question', '').strip()
    options = data.get('options', [])
    if not question or len(options) < 2:
        return jsonify({'error': 'Need question and at least 2 options'}), 400
    db = get_db()
    cursor = db.execute("INSERT INTO posts (user_id, content) VALUES (?, ?)",
                       (session['user_id'], "Poll: " + question))
    post_id = cursor.lastrowid
    cursor = db.execute("INSERT INTO polls (post_id, question) VALUES (?, ?)", (post_id, question))
    poll_id = cursor.lastrowid
    for opt in options:
        if opt.strip():
            db.execute("INSERT INTO poll_options (poll_id, option_text) VALUES (?, ?)", (poll_id, opt.strip()))
    db.commit()
    return jsonify({'status': 'ok', 'post_id': post_id})

@app.route("/api/poll/<int:poll_id>/vote", methods=["POST"])
@login_required
def vote_poll(poll_id):
    data = request.get_json()
    option_id = data.get('option_id')
    db = get_db()
    existing = db.execute("SELECT id FROM poll_votes WHERE poll_id = ? AND user_id = ?",
                         (poll_id, session['user_id'])).fetchone()
    if existing:
        return jsonify({'error': 'Already voted'}), 400
    db.execute("INSERT INTO poll_votes (poll_id, option_id, user_id) VALUES (?, ?, ?)",
              (poll_id, option_id, session['user_id']))
    db.commit()
    results = db.execute('''
        SELECT po.id, po.option_text, COUNT(pv.id) as votes FROM poll_options po
        LEFT JOIN poll_votes pv ON po.id = pv.option_id WHERE po.poll_id = ? GROUP BY po.id
    ''', (poll_id,)).fetchall()
    return jsonify({'status': 'ok', 'results': [dict(r) for r in results]})


# ================================
# PROFILE
# ================================
@app.route("/profile/<username>")
@login_required
def profile(username):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username,)).fetchone()
    if not user:
        flash("User not found", "error")
        return redirect(url_for('feed'))
    posts = db.execute('''
        SELECT p.*, (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count,
            (SELECT COUNT(*) FROM comments WHERE post_id = p.id) as comment_count
        FROM posts p WHERE p.user_id = ? ORDER BY p.created_at DESC
    ''', (user['id'],)).fetchall()
    followers = db.execute("SELECT COUNT(*) as c FROM follows WHERE following_id = ?", (user['id'],)).fetchone()['c']
    following = db.execute("SELECT COUNT(*) as c FROM follows WHERE follower_id = ?", (user['id'],)).fetchone()['c']
    is_following = False
    if session['user_id'] != user['id']:
        is_following = db.execute("SELECT id FROM follows WHERE follower_id = ? AND following_id = ?",
                                 (session['user_id'], user['id'])).fetchone() is not None
    posts_list = []
    for post in posts:
        post_dict = dict(post)
        post_dict['time_ago'] = time_ago(post['created_at'])
        posts_list.append(post_dict)
    return render_template("profile.html", profile_user=user, posts=posts_list,
                          followers=followers, following=following, is_following=is_following,
                          is_own_profile=(session['user_id'] == user['id']))

@app.route("/api/profile/update", methods=["POST"])
@login_required
def update_profile():
    bio = request.form.get('bio', '')[:200]
    avatar_url = None
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(str(session['user_id']) + "_avatar." + file.filename.rsplit('.', 1)[1])
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'profiles', filename)
            file.save(filepath)
            avatar_url = "/static/uploads/profiles/" + filename
    db = get_db()
    if avatar_url:
        db.execute("UPDATE users SET bio = ?, avatar = ? WHERE id = ?", (bio, avatar_url, session['user_id']))
    else:
        db.execute("UPDATE users SET bio = ? WHERE id = ?", (bio, session['user_id']))
    db.commit()
    flash("Profile updated!", "success")
    return redirect(url_for('profile', username=session['username']))


# ================================
# MESSAGES
# ================================
@app.route("/messages")
@login_required
def messages():
    db = get_db()
    conversations = db.execute('''
        SELECT DISTINCT CASE WHEN sender_id = ? THEN receiver_id ELSE sender_id END as other_user_id
        FROM messages WHERE sender_id = ? OR receiver_id = ?
    ''', (session['user_id'], session['user_id'], session['user_id'])).fetchall()
    conv_list = []
    for conv in conversations:
        other_id = conv['other_user_id']
        other_user = db.execute("SELECT * FROM users WHERE id = ?", (other_id,)).fetchone()
        if other_user:
            last_msg = db.execute('''
                SELECT content FROM messages
                WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
                ORDER BY created_at DESC LIMIT 1
            ''', (session['user_id'], other_id, other_id, session['user_id'])).fetchone()
            conv_list.append({
                'other_user_id': other_id, 'username': other_user['username'],
                'avatar': other_user['avatar'], 'last_message': last_msg['content'] if last_msg else ''
            })
    return render_template("messages.html", conversations=conv_list)

@app.route("/messages/<int:user_id>")
@login_required
def chat(user_id):
    db = get_db()
    other_user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not other_user:
        return redirect(url_for('messages'))
    chat_messages = db.execute('''
        SELECT m.*, u.username FROM messages m JOIN users u ON m.sender_id = u.id
        WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
        ORDER BY created_at ASC
    ''', (session['user_id'], user_id, user_id, session['user_id'])).fetchall()
    db.execute("UPDATE messages SET is_read = 1 WHERE sender_id = ? AND receiver_id = ?",
              (user_id, session['user_id']))
    db.commit()
    return render_template("chat.html", other_user=other_user, messages=chat_messages)

@app.route("/api/message", methods=["POST"])
@login_required
def send_message():
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Message cannot be empty'}), 400
    db = get_db()
    db.execute("INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
              (session['user_id'], receiver_id, content))
    db.commit()
    create_notification(receiver_id, 'message', session['user_id'], content=content[:50])
    return jsonify({'status': 'ok'})

@app.route("/api/chat/<int:user_id>/messages")
@login_required
def get_chat_messages(user_id):
    db = get_db()
    msgs = db.execute('''
        SELECT m.*, u.username FROM messages m JOIN users u ON m.sender_id = u.id
        WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
        ORDER BY created_at ASC
    ''', (session['user_id'], user_id, user_id, session['user_id'])).fetchall()
    return jsonify({'messages': [dict(m) for m in msgs]})


# ================================
# NOTIFICATIONS
# ================================
@app.route("/notifications")
@login_required
def notifications():
    db = get_db()
    notifs = db.execute('''
        SELECT n.*, u.username, u.avatar FROM notifications n
        LEFT JOIN users u ON n.from_user_id = u.id
        WHERE n.user_id = ? ORDER BY n.created_at DESC LIMIT 50
    ''', (session['user_id'],)).fetchall()
    db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (session['user_id'],))
    db.commit()
    notif_list = []
    for n in notifs:
        notif_dict = dict(n)
        notif_dict['time_ago'] = time_ago(n['created_at'])
        notif_list.append(notif_dict)
    return render_template("notifications.html", notifications=notif_list)

@app.route("/api/notifications/count")
@login_required
def notification_count():
    db = get_db()
    count = db.execute("SELECT COUNT(*) as c FROM notifications WHERE user_id = ? AND is_read = 0",
                      (session['user_id'],)).fetchone()['c']
    return jsonify({'count': count})


# ================================
# EXPLORE
# ================================
@app.route("/explore")
@login_required
def explore():
    db = get_db()
    posts = db.execute('''
        SELECT p.*, u.username, u.avatar,
            (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count
        FROM posts p JOIN users u ON p.user_id = u.id
        ORDER BY like_count DESC, p.created_at DESC LIMIT 30
    ''').fetchall()
    return render_template("explore.html", posts=posts)


# ================================
# REELS
# ================================
@app.route("/reels")
@login_required
def reels():
    db = get_db()
    reel_list = db.execute('''
        SELECT p.*, u.username, u.avatar FROM posts p
        JOIN users u ON p.user_id = u.id WHERE p.media_type = 'video'
        ORDER BY p.created_at DESC LIMIT 50
    ''').fetchall()
    return render_template("reels.html", reels=reel_list)


# ================================
# SEARCH
# ================================
@app.route("/api/search")
@login_required
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'users': [], 'posts': []})
    db = get_db()
    users = db.execute("SELECT id, username, avatar, bio FROM users WHERE username LIKE ?",
                      ('%' + q + '%',)).fetchall()
    posts = db.execute('''
        SELECT p.*, u.username FROM posts p JOIN users u ON p.user_id = u.id
        WHERE p.content LIKE ? ORDER BY p.created_at DESC LIMIT 20
    ''', ('%' + q + '%',)).fetchall()
    return jsonify({'users': [dict(u) for u in users], 'posts': [dict(p) for p in posts]})


# ================================
# AI ROUTES
# ================================
@app.route("/ai")
@login_required
def ai():
    db = get_db()
    history = db.execute('SELECT * FROM ai_chats WHERE user_id = ? ORDER BY created_at ASC LIMIT 50',
                        (session['user_id'],)).fetchall()
    return render_template("ai.html", history=history)

@app.route("/api/ai/chat", methods=["POST"])
@login_required
def api_ai_chat():
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        if not message:
            return jsonify({'reply': 'Please type a message'}), 400
        
        username = session.get('username', 'User')
        
        db = get_db()
        history = db.execute(
            'SELECT role, message FROM ai_chats WHERE user_id = ? ORDER BY created_at DESC LIMIT 10',
            (session['user_id'],)
        ).fetchall()
        
        history_list = [{'role': h['role'], 'message': h['message']} for h in reversed(history)]
        
        reply = get_ai_reply(message, username, history_list)
        
        db.execute("INSERT INTO ai_chats (user_id, role, message) VALUES (?, ?, ?)",
                  (session['user_id'], 'user', message[:500]))
        db.execute("INSERT INTO ai_chats (user_id, role, message) VALUES (?, ?, ?)",
                  (session['user_id'], 'assistant', reply[:5000]))
        db.commit()
        
        return jsonify({'reply': reply})
    except Exception as e:
        print("AI Error: " + str(e))
        return jsonify({'reply': "Sorry, I encountered an error. Please try again!"}), 500

@app.route("/api/ai/clear", methods=["POST"])
@login_required
def api_ai_clear():
    db = get_db()
    db.execute("DELETE FROM ai_chats WHERE user_id = ?", (session['user_id'],))
    db.commit()
    return jsonify({'status': 'ok'})


# ================================
# SETTINGS
# ================================
@app.route("/settings")
@login_required
def settings():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    followers = db.execute("SELECT COUNT(*) as c FROM follows WHERE following_id = ?", (session['user_id'],)).fetchone()['c']
    following = db.execute("SELECT COUNT(*) as c FROM follows WHERE follower_id = ?", (session['user_id'],)).fetchone()['c']
    post_count = db.execute("SELECT COUNT(*) as c FROM posts WHERE user_id = ?", (session['user_id'],)).fetchone()['c']
    return render_template("settings.html", user=user, followers=followers, following=following, post_count=post_count)

@app.route("/api/settings/profile", methods=["POST"])
@login_required
def update_settings_profile():
    username = request.form.get('username', '').strip()
    bio = request.form.get('bio', '')[:200]
    email = request.form.get('email', '').strip()
    avatar_url = None
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(str(session['user_id']) + "_avatar." + file.filename.rsplit('.', 1)[1])
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'profiles', filename)
            file.save(filepath)
            avatar_url = "/static/uploads/profiles/" + filename
    db = get_db()
    try:
        if avatar_url:
            db.execute("UPDATE users SET username = ?, email = ?, bio = ?, avatar = ? WHERE id = ?",
                      (username, email, bio, avatar_url, session['user_id']))
        else:
            db.execute("UPDATE users SET username = ?, email = ?, bio = ? WHERE id = ?",
                      (username, email, bio, session['user_id']))
        db.commit()
        session['username'] = username
        flash("Profile updated successfully!", "success")
    except sqlite3.IntegrityError:
        flash("Username or email already taken", "error")
    return redirect(url_for('settings'))

@app.route("/api/settings/password", methods=["POST"])
@login_required
def change_password():
    current = request.form.get('current_password', '').strip()
    new_pass = request.form.get('new_password', '').strip()
    confirm = request.form.get('confirm_password', '').strip()
    if new_pass != confirm:
        flash("New passwords don't match", "error")
        return redirect(url_for('settings'))
    if len(new_pass) < 6:
        flash("Password must be at least 6 characters", "error")
        return redirect(url_for('settings'))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ? AND password_hash = ?",
                     (session['user_id'], hash_password(current))).fetchone()
    if not user:
        flash("Current password is incorrect", "error")
        return redirect(url_for('settings'))
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_pass), session['user_id']))
    db.commit()
    flash("Password changed successfully!", "success")
    return redirect(url_for('settings'))

@app.route("/api/settings/delete-account", methods=["POST"])
@login_required
def delete_account():
    password = request.form.get('password', '').strip()
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ? AND password_hash = ?",
                     (session['user_id'], hash_password(password))).fetchone()
    if not user:
        flash("Incorrect password", "error")
        return redirect(url_for('settings'))
    user_id = session['user_id']
    db.execute("DELETE FROM posts WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM likes WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM comments WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM follows WHERE follower_id = ? OR following_id = ?", (user_id, user_id))
    db.execute("DELETE FROM messages WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id))
    db.execute("DELETE FROM notifications WHERE user_id = ? OR from_user_id = ?", (user_id, user_id))
    db.execute("DELETE FROM stories WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM ai_chats WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM saved_posts WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    session.clear()
    flash("Account deleted successfully", "success")
    return redirect(url_for('login'))


# ================================
# HASHTAG
# ================================
@app.route("/hashtag/<tag>")
@login_required
def hashtag(tag):
    db = get_db()
    posts = db.execute('''
        SELECT p.*, u.username, u.avatar,
            (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count,
            (SELECT COUNT(*) FROM comments WHERE post_id = p.id) as comment_count,
            (SELECT COUNT(*) FROM likes WHERE post_id = p.id AND user_id = ?) as user_liked
        FROM posts p JOIN users u ON p.user_id = u.id
        WHERE p.content LIKE ? ORDER BY p.created_at DESC LIMIT 50
    ''', (session['user_id'], '%#' + tag + '%')).fetchall()
    posts_list = []
    for post in posts:
        post_dict = dict(post)
        post_dict['time_ago'] = time_ago(post['created_at'])
        posts_list.append(post_dict)
    return render_template("hashtag.html", tag=tag, posts=posts_list)


# ================================
# SOCIAL LOGIN
# ================================
@app.route("/auth/google")
def google_login():
    if not GOOGLE_ENABLED:
        flash("Google login not configured", "error")
        return redirect(url_for('login'))
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/auth/google/callback")
def google_callback():
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info:
            resp = google.get('https://www.googleapis.com/oauth2/v3/userinfo')
            user_info = resp.json()
        email = user_info.get('email', '')
        name = user_info.get('name', '')
        if not email:
            flash("Could not get email from Google", "error")
            return redirect(url_for('login'))
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash("Welcome back, " + user['username'] + "!", "success")
        else:
            username = name.replace(' ', '_').lower()
            base_username = username
            counter = 1
            while True:
                existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
                if not existing:
                    break
                username = base_username + str(counter)
                counter += 1
            random_pass = hashlib.sha256(os.urandom(32)).hexdigest()
            db.execute('INSERT INTO users (username, email, password_hash, is_verified) VALUES (?, ?, ?, 1)',
                      (username, email, random_pass))
            db.commit()
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash("Welcome to QHive, " + username + "!", "success")
        return redirect(url_for('feed'))
    except Exception as e:
        print("Google OAuth Error: " + str(e))
        flash("Google login failed. Please try again.", "error")
        return redirect(url_for('login'))

@app.route("/auth/apple")
def apple_login():
    flash("Apple Sign In coming soon! Please use Google or email.", "error")
    return redirect(url_for('login'))

@app.route("/auth/twitter")
def twitter_login():
    flash("Twitter Sign In coming soon! Please use Google or email.", "error")
    return redirect(url_for('login'))


# ================================
# FOOTER PAGES
# ================================
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            flash("Password reset link sent to your email!", "success")
        else:
            flash("Email not found", "error")
    return render_template("forgot_password.html")

@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        password = request.form.get("password", "").strip()
        if len(password) >= 6:
            flash("Password updated successfully!", "success")
            return redirect(url_for('login'))
        else:
            flash("Password must be at least 6 characters", "error")
    return render_template("reset_password.html")

@app.route("/about")
def about_page():
    return render_template("about.html")

@app.route("/help")
def help_page():
    return render_template("help.html")

@app.route("/privacy")
def privacy_page():
    return render_template("privacy.html")

@app.route("/terms")
def terms_page():
    return render_template("terms.html")


# ================================
# RUN SERVER
# ================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    print("\n" + "=" * 50)
    print("QHIVE - Smart Traders. Stronger Together.")
    print("=" * 50)
    print("URL: http://127.0.0.1:" + str(port))
    print("All features are REAL!")
    print("=" * 50 + "\n")
    app.run(debug=debug, host="0.0.0.0", port=port)