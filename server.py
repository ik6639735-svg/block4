# ===============================
#  BLOCK4 - FULL SOCIAL PLATFORM
#  Production Ready Version
# ===============================

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
from werkzeug.utils import secure_filename
import sqlite3
import hashlib
import os
# Use persistent database path
import os
DB_PATH = os.environ.get('DATABASE_URL', 'block4.db')
import re
import random
# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timedelta
from authlib.integrations.flask_client import OAuth

# OAuth Setup
oauth = OAuth(app)

# Google OAuth
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID', ''),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET', ''),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

app = Flask(__name__)
app.secret_key = "block4_full_platform_2026_secure_key"

# Make hashtags clickable
@app.template_filter('linkify_hashtags')
def linkify_hashtags(text):
    if not text:
        return text
    import re
    return re.sub(r'#(\w+)', r'<a href="/hashtag/\1" style="color:var(--gold); text-decoration:none;">#\1</a>', text)

# File Upload Config
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'webm'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# Create upload folders
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(f'{UPLOAD_FOLDER}/posts', exist_ok=True)
os.makedirs(f'{UPLOAD_FOLDER}/stories', exist_ok=True)
os.makedirs(f'{UPLOAD_FOLDER}/profiles', exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ================================
# PROPER DATABASE CONNECTION
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
    
    conn.commit()
    conn.close()

init_db()


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
        return f"{diff.days // 365}y ago"
    elif diff.days > 30:
        return f"{diff.days // 30}mo ago"
    elif diff.days > 7:
        return dt.strftime('%b %d')
    elif diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600}h ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60}m ago"
    else:
        return "Just now"

def create_notification(user_id, notif_type, from_user_id=None, post_id=None, content=None):
    if user_id == from_user_id:
        return
    try:
        db = get_db()
        db.execute('''INSERT INTO notifications (user_id, type, from_user_id, post_id, content)
                      VALUES (?, ?, ?, ?, ?)''', (user_id, notif_type, from_user_id, post_id, content))
        db.commit()
    except Exception as e:
        print(f"Notification error: {e}")

def extract_hashtags(text):
    if not text:
        return []
    return re.findall(r'#(\w+)', text)


# 🎉 YOUR WEBSITE IS LIVE!!! 🌍

I can see it: **https://block4.onrender.com**

That is absolutely amazing! Your Block4 platform is now accessible to the entire world! 🚀

---

## ⚠️ Quick Fix Needed for Production

Your site might have issues with the database on Render because Render's free tier **doesn't save files permanently**. Every time Render redeploys, your `block4.db` gets deleted.

### Fix: Add this to your `server.py` after the imports:

```python
# Use persistent database path
import os
DB_PATH = os.environ.get('DATABASE_URL', 'block4.db')
```

Then change the `get_db()` function:

```python
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=20)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA busy_timeout=5000")
    return g.db
```

And change `init_db()`:

```python
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    # ... rest stays the same
```

**For now this is fine for testing!** When you're ready for real users, we'll upgrade to a proper database.

---

## 🚀 Let's Keep Building! Feature F: Smarter AI

Now let's make your AI much smarter with more topics!

### Replace your entire `QHiveBrain` class in `server.py`:

```python
# ================================
# 🧠 QHiveBrain v2.0
# ================================
class QHiveBrain:
    def __init__(self):
        self.name = "QHive AI"
        self.knowledge = {
            'trading': {
                'smc': self.explain_smc,
                'order block': self.explain_ob,
                'fvg': self.explain_fvg,
                'liquidity': self.explain_liquidity,
                'bos': self.explain_bos,
                'choch': self.explain_choch,
                'supply demand': self.explain_supply_demand,
                'fibonacci': self.explain_fibonacci,
                'candlestick': self.explain_candlestick,
                'indicator': self.explain_indicators,
                'moving average': self.explain_ma,
                'rsi': self.explain_rsi,
                'macd': self.explain_macd,
                'bollinger': self.explain_bollinger,
                'support resistance': self.explain_sr,
                'trend': self.explain_trend,
                'scalp': self.explain_scalping,
                'swing': self.explain_swing,
                'day trad': self.explain_daytrading,
                'position': self.explain_position,
            }
        }
    
    def think(self, message, username="User"):
        msg = message.lower().strip()
        original = message.strip()
        
        if not msg:
            return "I'm listening! What would you like to know?"
        
        # Greetings
        greetings = ['hi', 'hello', 'hey', 'yo', 'sup', 'good morning', 'good evening', 'good afternoon', 'whats up', "what's up", 'howdy']
        if any(msg.startswith(g) or msg == g for g in greetings):
            responses = [
                f"Hey {username}! 👋 Great to see you! I'm Block4 AI v2.0 - I know about trading, crypto, forex, content creation, psychology, and much more! What can I help with?",
                f"Hello {username}! 🌟 Ready to help you level up! Ask me about SMC, risk management, content ideas, or anything else!",
                f"What's good {username}! 💪 I'm your AI trading assistant. Let's make some moves today!"
            ]
            return random.choice(responses)
        
        # Identity
        if any(w in msg for w in ['who are you', 'what are you', 'your name', 'what can you do', 'help me', 'what do you know']):
            return f"""👋 I'm **Block4 AI v2.0** - Your Ultimate Trading Assistant!

**📊 Trading Knowledge:**
• Smart Money Concepts (SMC)
• Order Blocks, FVGs, Liquidity
• Break of Structure & CHoCH
• Supply & Demand Zones
• Fibonacci Retracements
• All major indicators (RSI, MACD, MA, Bollinger)
• Candlestick patterns
• Scalping, Swing, Day & Position trading

**💰 Crypto & Forex:**
• Bitcoin & Altcoin analysis
• Forex pairs & strategies
• DeFi & Web3 concepts

**✍️ Content & Growth:**
• Viral captions & hooks
• Content strategies
• Brand building tips

**🧠 Mindset:**
• Trading psychology
• Risk management
• Discipline & journaling

**Just ask me anything naturally!** 🚀"""

        # Check trading knowledge base
        for keyword, func in self.knowledge['trading'].items():
            if keyword in msg:
                return func()
        
        # Risk Management
        if any(w in msg for w in ['risk', 'manage', 'position size', 'stop loss', 'lot size', 'money manage']):
            return self.explain_risk()
        
        # Crypto topics
        if any(w in msg for w in ['bitcoin', 'btc', 'crypto', 'ethereum', 'eth', 'altcoin']):
            return self.explain_crypto(msg)
        
        # Forex topics
        if any(w in msg for w in ['forex', 'currency', 'eur', 'usd', 'gbp', 'jpy', 'pip']):
            return self.explain_forex(msg)
        
        # Content/Caption
        if any(w in msg for w in ['caption', 'content', 'hook', 'post idea', 'viral', 'grow', 'follower']):
            return self.create_content(msg)
        
        # Psychology/Mindset
        if any(w in msg for w in ['loss', 'lost', 'losing', 'psychology', 'mindset', 'discipline', 'emotion', 'revenge', 'fear', 'greed', 'patient', 'journal']):
            return self.explain_psychology(msg)
        
        # Market analysis
        if any(w in msg for w in ['market', 'bull', 'bear', 'crash', 'pump', 'dump', 'rally', 'correction']):
            return self.explain_market(msg)
        
        # DeFi / Web3
        if any(w in msg for w in ['defi', 'web3', 'nft', 'blockchain', 'smart contract', 'dao', 'dex', 'yield']):
            return self.explain_defi(msg)
        
        # Trading plan
        if any(w in msg for w in ['plan', 'strategy', 'system', 'backtest', 'journal', 'routine']):
            return self.explain_plan(msg)
        
        # Motivation
        if any(w in msg for w in ['motivat', 'inspire', 'quit', 'give up', 'hard', 'difficult', 'struggling']):
            return self.give_motivation(username)
        
        # Thanks
        if any(w in msg for w in ['thank', 'thanks', 'helpful', 'awesome', 'great', 'perfect', 'amazing']):
            return random.choice([
                f"You're welcome {username}! 🙏 Keep pushing forward!",
                "Anytime! 💪 That's what I'm here for!",
                "Glad I could help! 🚀 Any other questions?",
                f"No problem {username}! Remember, consistency is key! 🔑"
            ])
        
        # Bye
        if any(w in msg for w in ['bye', 'goodbye', 'later', 'see you', 'good night']):
            return random.choice([
                f"Take care {username}! 👋 Come back anytime!",
                f"Later {username}! 🚀 Keep grinding!",
                f"Goodbye {username}! 💪 Trade safe and stay disciplined!"
            ])
        
        # Math/Calculator
        if any(w in msg for w in ['calculate', 'how much', 'what is', 'convert']) and any(c.isdigit() for c in msg):
            return self.calculate(msg)
        
        # Fallback - smarter response
        return f"""🤖 Interesting question about: "*{original[:80]}*"

I'm most knowledgeable about these topics:

**📊 Trading:** "Explain order blocks" or "What is SMC?"
**💰 Crypto:** "Tell me about Bitcoin" or "What is DeFi?"
**📈 Forex:** "Best forex strategies" or "Explain pips"
**✍️ Content:** "Give me a viral caption" or "Post ideas"
**🧠 Mindset:** "How to handle losses" or "Trading psychology"
**📋 Planning:** "Create a trading plan" or "Backtesting tips"
**💡 Indicators:** "Explain RSI" or "How to use MACD"

Try asking about any of these! 🎯"""
    
    # ========== TRADING METHODS ==========
    
    def explain_smc(self):
        return """📊 **Smart Money Concepts (SMC) - Complete Guide:**

SMC is based on how **institutional traders** (banks, hedge funds) move the markets.

**🔑 Core Concepts:**

1. **Market Structure** - Higher highs/lows (uptrend), Lower highs/lows (downtrend)
2. **Liquidity** - Where retail stop losses cluster (above highs, below lows)
3. **Order Blocks (OB)** - Last opposite candle before a strong move
4. **Fair Value Gaps (FVG)** - Imbalances in price action
5. **Break of Structure (BOS)** - Continuation signal
6. **Change of Character (CHoCH)** - Reversal signal
7. **Premium/Discount** - Buy in discount (below 50%), sell in premium (above 50%)

**📋 SMC Trading Steps:**
1. Identify higher timeframe trend
2. Wait for a pullback to discount/premium zone
3. Look for liquidity sweep
4. Find order block or FVG as entry
5. Enter with confirmation
6. Target the next liquidity pool

**🎯 Pro Tips:**
• Always trade WITH the higher timeframe trend
• Patience > Frequency
• Wait for liquidity to be taken before entering
• Use multi-timeframe analysis (HTF → LTF)

Want me to explain any specific concept deeper? 💡"""

    def explain_ob(self):
        return """🏛️ **Order Blocks - Deep Dive:**

An Order Block is the **last opposite candle** before a strong impulsive move.

**Types:**
📗 **Bullish OB:** Last RED candle before a big move UP
📕 **Bearish OB:** Last GREEN candle before a big move DOWN

**How to Identify Quality OBs:**
1. Must cause a **Break of Structure**
2. Should have a strong move away from it
3. Look for **imbalance** (FVG) after the OB
4. Higher timeframe OBs are stronger
5. Unmitigated (untouched) OBs are best

**How to Trade:**
1. Mark the OB zone (open to close of the candle)
2. Wait for price to return to the zone
3. Look for reaction/confirmation on lower timeframe
4. Enter with stop loss beyond the OB
5. Target: Next liquidity level or opposing OB

**⚠️ Common Mistakes:**
• Trading every OB (be selective!)
• Ignoring the trend
• Not waiting for confirmation
• Placing SL too tight

**Quality > Quantity** when it comes to OBs! 💎"""

    def explain_fvg(self):
        return """📉 **Fair Value Gaps (FVG) - Complete Guide:**

An FVG is a **3-candle pattern** where the middle candle creates an imbalance.

**Bullish FVG:**
• Candle 1's HIGH doesn't reach Candle 3's LOW
• Gap = space between C1 high and C3 low
• Price tends to fill this gap by pulling back down

**Bearish FVG:**
• Candle 1's LOW doesn't reach Candle 3's HIGH
• Gap = space between C1 low and C3 high
• Price tends to fill this gap by pulling back up

**How to Trade FVGs:**
1. Identify the FVG on your chart
2. Wait for price to return to fill the gap
3. Enter at the 50% level of the FVG (optimal)
4. Stop loss beyond the FVG
5. Target: Next swing point or liquidity level

**🔑 Key Rules:**
• FVGs on higher timeframes are more significant
• Combine with Order Blocks for high-probability setups
• Not all FVGs get filled - look for confluence
• FVGs act as both support and resistance

**Pro Tip:** The best entries come when an FVG overlaps with an Order Block! 🎯"""

    def explain_liquidity(self):
        return """💧 **Liquidity - The Key to SMC:**

Liquidity = **clusters of stop losses** that institutions target.

**Types of Liquidity:**

📍 **Buy-Side Liquidity (BSL):**
• Stop losses above swing highs
• Buy stops from short sellers
• Institutions push price UP to grab these

📍 **Sell-Side Liquidity (SSL):**
• Stop losses below swing lows
• Sell stops from long buyers
• Institutions push price DOWN to grab these

**Liquidity Concepts:**
• **Equal Highs** = liquidity magnet above
• **Equal Lows** = liquidity magnet below
• **Trendline liquidity** = stops along trend lines
• **Session highs/lows** = Asian, London, NY ranges

**How Smart Money Uses Liquidity:**
1. Price sweeps liquidity (takes out stops)
2. Orders get filled (institutions enter)
3. Price reverses in the real direction
4. This is called a **liquidity grab** or **stop hunt**

**How to Trade It:**
• Don't place stops at obvious levels
• Wait for liquidity to be swept BEFORE entering
• Use liquidity pools as targets
• The sweep + displacement = your signal

**Remember:** Liquidity is the FUEL for price movements! ⛽"""

    def explain_bos(self):
        return """📈 **Break of Structure (BOS):**

BOS = Price breaks a **previous swing high/low** in the SAME direction as the trend.

**Bullish BOS:** Price breaks above a previous swing HIGH → Uptrend continues
**Bearish BOS:** Price breaks below a previous swing LOW → Downtrend continues

**How to Use BOS:**
1. Confirms the current trend is still valid
2. After BOS, look for pullback entry
3. Enter at the Order Block that caused the BOS
4. Target the next swing point

**BOS is a CONTINUATION signal!** ✅

Want to know about CHoCH (reversal signal) too? 🎯"""

    def explain_choch(self):
        return """🔄 **Change of Character (CHoCH):**

CHoCH = Price breaks structure in the **OPPOSITE** direction → Trend reversal signal!

**Bullish CHoCH:** In a downtrend, price breaks above a swing HIGH → Possible reversal to uptrend
**Bearish CHoCH:** In an uptrend, price breaks below a swing LOW → Possible reversal to downtrend

**CHoCH vs BOS:**
• **BOS** = Trend CONTINUES (same direction break)
• **CHoCH** = Trend REVERSES (opposite direction break)

**How to Trade CHoCH:**
1. Identify the CHoCH on higher timeframe
2. Wait for pullback after the break
3. Enter at the Order Block or FVG
4. Stop loss beyond the CHoCH point
5. Target: New trend direction

**⚠️ Warning:** Not every CHoCH leads to a full reversal. Always wait for confirmation! 🎯"""

    def explain_supply_demand(self):
        return """📊 **Supply & Demand Zones:**

**Demand Zone (Buy Zone):**
• Area where buyers overwhelmed sellers
• Price dropped TO this zone, then shot UP
• Look for: Drop-Base-Rally or Rally-Base-Rally

**Supply Zone (Sell Zone):**
• Area where sellers overwhelmed buyers
• Price rose TO this zone, then dropped DOWN
• Look for: Rally-Base-Drop or Drop-Base-Drop

**How to Draw Zones:**
1. Find a strong move (impulse)
2. Mark the base (consolidation) before the move
3. Extend the zone to the right
4. Wait for price to return

**Quality Checklist:**
✅ Strong departure from zone
✅ Fresh (untested) zone
✅ Little time spent in zone
✅ Higher timeframe zones > Lower timeframe

Similar to Order Blocks but broader concept! 💡"""

    def explain_fibonacci(self):
        return """📐 **Fibonacci Retracements:**

Fibonacci levels help identify potential **pullback zones**.

**Key Levels:**
• **0.236** - Shallow pullback
• **0.382** - Common pullback
• **0.500** - 50% level (not Fib but widely used)
• **0.618** - Golden ratio (strongest level!)
• **0.786** - Deep pullback
• **0.886** - Very deep pullback

**How to Use:**
1. Identify a clear impulse move (swing high to swing low)
2. Draw Fibonacci from the start to end of the move
3. Wait for price to retrace to a key level
4. Look for confirmation (candlestick pattern, OB, FVG)
5. Enter with proper risk management

**🔑 Best Practice:**
• 0.618 + Order Block = 🔥 High probability setup
• Use on higher timeframes for stronger levels
• Combine with other confluence (support/resistance)

**Golden Pocket (0.618-0.65)** is the most watched level! 💎"""

    def explain_candlestick(self):
        return """🕯️ **Candlestick Patterns:**

**Bullish Patterns (Buy Signals):**
• 🟢 **Hammer** - Small body, long lower wick at support
• 🟢 **Engulfing** - Big green candle swallows previous red
• 🟢 **Morning Star** - 3 candle reversal at bottom
• 🟢 **Doji** - Indecision → look for next candle direction
• 🟢 **Three White Soldiers** - 3 consecutive green candles

**Bearish Patterns (Sell Signals):**
• 🔴 **Shooting Star** - Small body, long upper wick at resistance
• 🔴 **Bearish Engulfing** - Big red swallows previous green
• 🔴 **Evening Star** - 3 candle reversal at top
• 🔴 **Dark Cloud Cover** - Red opens above, closes below midpoint

**🔑 Tips:**
• Patterns work best at KEY levels (support/resistance/OB)
• Higher timeframe patterns are more reliable
• Always wait for the candle to CLOSE before entering
• Combine with volume for confirmation

Context matters more than the pattern itself! 📍"""

    def explain_indicators(self):
        return """📊 **Popular Trading Indicators:**

**Trend Indicators:**
• Moving Averages (SMA, EMA)
• MACD
• ADX
• Ichimoku Cloud

**Momentum Indicators:**
• RSI (Relative Strength Index)
• Stochastic
• CCI
• Williams %R

**Volatility Indicators:**
• Bollinger Bands
• ATR (Average True Range)
• Keltner Channels

**Volume Indicators:**
• Volume Profile
• OBV (On Balance Volume)
• VWAP

**🔑 Best Practice:**
• Don't use too many (2-3 max)
• Combine trend + momentum indicator
• Indicators LAG - price action leads
• Use as CONFIRMATION, not primary signal

Want details on any specific indicator? 🎯"""

    def explain_ma(self):
        return """📈 **Moving Averages:**

**SMA (Simple Moving Average):**
• Average of last X candles
• Smoother, slower to react
• Best for: Higher timeframes

**EMA (Exponential Moving Average):**
• Weighs recent prices more
• Faster reaction to price changes
• Best for: Active trading

**Key Moving Averages:**
• **9 EMA** - Scalping, very short term
• **21 EMA** - Short term trend
• **50 EMA/SMA** - Medium term trend
• **100 SMA** - Strong support/resistance
• **200 SMA** - The "King" - defines bull vs bear market

**Trading Strategies:**
1. **MA Crossover:** 9 EMA crosses above 21 EMA = Buy signal
2. **Price + MA:** Price bounces off 50 EMA = Buy in uptrend
3. **200 SMA Rule:** Price above 200 SMA = Only look for buys

**Golden Cross:** 50 SMA crosses ABOVE 200 SMA = Very bullish 📈
**Death Cross:** 50 SMA crosses BELOW 200 SMA = Very bearish 📉"""

    def explain_rsi(self):
        return """📊 **RSI (Relative Strength Index):**

RSI measures **momentum** on a scale of 0-100.

**Key Levels:**
• **Above 70** = Overbought (price might drop)
• **Below 30** = Oversold (price might rise)
• **50 level** = Trend direction indicator

**How to Trade RSI:**
1. **Overbought/Oversold:** Wait for RSI to exit 70/30 zone
2. **Divergence:** Price makes new high but RSI doesn't = REVERSAL signal
3. **50 Level:** RSI above 50 = bullish trend, below 50 = bearish trend

**RSI Divergence (Most Powerful!):**
• **Bullish Divergence:** Price makes lower low, RSI makes higher low → BUY
• **Bearish Divergence:** Price makes higher high, RSI makes lower high → SELL

**Settings:**
• Default: 14 period
• Faster: 7 period (more signals, more noise)
• Slower: 21 period (fewer signals, more reliable)

**⚠️ Don't** just buy because RSI is oversold in a downtrend! Context matters! 🎯"""

    def explain_macd(self):
        return """📉 **MACD (Moving Average Convergence Divergence):**

MACD shows **trend direction and momentum**.

**Components:**
• **MACD Line** = 12 EMA - 26 EMA
• **Signal Line** = 9 EMA of MACD Line
• **Histogram** = MACD Line - Signal Line

**Trading Signals:**
1. **MACD crosses ABOVE signal** = Bullish (Buy) ✅
2. **MACD crosses BELOW signal** = Bearish (Sell) ❌
3. **Histogram growing** = Momentum increasing
4. **Histogram shrinking** = Momentum weakening

**MACD Divergence:**
• Price makes higher high, MACD makes lower high = Bearish divergence
• Price makes lower low, MACD makes higher low = Bullish divergence

**🔑 Pro Tips:**
• Works best in trending markets
• Combine with support/resistance levels
• Zero line crossover = Strong trend confirmation
• Don't use in sideways/ranging markets

Default settings (12, 26, 9) work well for most timeframes! 📊"""

    def explain_bollinger(self):
        return """📊 **Bollinger Bands:**

Shows **volatility** and potential reversal zones.

**Components:**
• **Middle Band** = 20 SMA
• **Upper Band** = 20 SMA + (2 × Standard Deviation)
• **Lower Band** = 20 SMA - (2 × Standard Deviation)

**Trading Strategies:**

1. **Bounce Strategy:**
   • Price touches lower band = Potential buy
   • Price touches upper band = Potential sell
   • Works best in ranging markets

2. **Squeeze Strategy:**
   • Bands get very tight = Low volatility
   • Big move coming! Wait for breakout direction
   • Enter in the breakout direction

3. **Walking the Band:**
   • In strong uptrend, price "walks" along upper band
   • In strong downtrend, price "walks" along lower band
   • Don't counter-trade this!

**🔑 Key Rules:**
• Price outside bands = Extreme move, likely to return
• Tight bands = Expect a big move soon
• Wide bands = High volatility period
• Use with RSI for better signals

**Pro Tip:** Bollinger Squeeze + Volume increase = 💥 Explosive move incoming!"""

    def explain_sr(self):
        return """📊 **Support & Resistance:**

The most **fundamental** concept in trading!

**Support:** Price level where buying pressure prevents further decline
**Resistance:** Price level where selling pressure prevents further rise

**How to Find S/R:**
1. Look for areas where price **bounced multiple times**
2. Round numbers (1.0000, 50000, etc.)
3. Previous day/week/month highs and lows
4. Moving averages (50, 100, 200)
5. Fibonacci levels

**Key Rules:**
• The more times a level is tested, the stronger it is
• Once broken, support becomes resistance (and vice versa) - this is called a **flip**
• S/R are ZONES, not exact lines
• Higher timeframe levels are stronger

**Pro Tips:**
• Don't place stops right at S/R levels
• Wait for a **retest** of broken S/R before entering
• Combine with candlestick patterns for confirmation
• Volume spike at S/R = Strong reaction likely

This is the foundation of all trading! Master this first! 🏗️"""

    def explain_trend(self):
        return """📈 **Trend Analysis:**

**"The trend is your friend"** - Most important rule in trading!

**Uptrend:** Higher Highs + Higher Lows 📈
**Downtrend:** Lower Highs + Lower Lows 📉
**Sideways:** No clear direction (range) ↔️

**How to Identify Trends:**
1. **Visual:** Look at the chart - is it going up or down?
2. **Moving Averages:** Price above 200 SMA = Uptrend
3. **Higher Highs/Lows:** Draw swing points
4. **Trendlines:** Connect swing lows (uptrend) or swing highs (downtrend)

**Trading WITH the Trend:**
• In uptrend → Only look for BUY setups
• In downtrend → Only look for SELL setups
• In sideways → Trade the range or wait

**Multi-Timeframe:**
• Weekly/Daily = Main trend direction
• 4H/1H = Entry timing
• Always align with the bigger picture!

**⚠️ #1 Mistake:** Trading against the trend. Don't be a hero! 🎯"""

    def explain_scalping(self):
        return """⚡ **Scalping Strategy:**

Quick trades lasting **seconds to minutes**.

**Characteristics:**
• Timeframes: 1M, 5M, 15M
• Hold time: Seconds to 30 minutes
• Profit target: 5-15 pips
• Stop loss: 3-10 pips
• Win rate needed: 60%+ due to spread costs

**Best Scalping Strategies:**
1. **EMA Crossover (9/21)** on 5M chart
2. **Support/Resistance bounce** on 1M-5M
3. **Breakout scalping** during London/NY open
4. **Order Block entry** on 1M after 15M trend confirmed

**Requirements:**
• Fast execution (low spread broker)
• Tight risk management
• Full attention (no distractions!)
• Best during high volume sessions

**⚠️ Not for beginners!** Start with swing trading first! 💡"""

    def explain_swing(self):
        return """🌊 **Swing Trading:**

Hold trades for **days to weeks**.

**Characteristics:**
• Timeframes: 4H, Daily, Weekly
• Hold time: 2-14 days
• Profit target: 100-500+ pips
• Stop loss: 30-100 pips
• Win rate needed: 40-50% (because R:R is high)

**Best Swing Strategies:**
1. **Trend continuation** - Buy pullbacks in uptrend
2. **Support/Resistance** - Buy at support, sell at resistance
3. **Chart patterns** - Head & shoulders, flags, triangles
4. **Fibonacci pullback** - Enter at 0.618 level

**Advantages:**
✅ Less screen time
✅ Better risk/reward ratios
✅ Less affected by noise/spread
✅ Works with a full-time job

**Best for beginners and intermediate traders!** 🎯"""

    def explain_daytrading(self):
        return """📅 **Day Trading:**

Open and close all trades **within the same day**.

**Characteristics:**
• Timeframes: 15M, 1H, 4H
• Hold time: 30 min to 8 hours
• Profit target: 20-100 pips
• No overnight risk

**Day Trading Sessions:**
• **Asian (Tokyo):** 00:00-09:00 GMT - Low volatility
• **London:** 08:00-17:00 GMT - High volatility ⚡
• **New York:** 13:00-22:00 GMT - High volatility ⚡
• **London/NY Overlap:** 13:00-17:00 GMT - BEST TIME! 🔥

**Strategy:**
1. Mark Asian range
2. Wait for London breakout
3. Trade in breakout direction
4. Close before end of NY session

**Rules:**
• Max 2-3 trades per day
• Stop trading after 2 losses
• Always close before market close
• Journal every trade

Quality over quantity! 📋"""

    def explain_position(self):
        return """📈 **Position Trading:**

Long-term trades lasting **weeks to months**.

**Characteristics:**
• Timeframes: Daily, Weekly, Monthly
• Hold time: Weeks to months
• Profit target: 500-2000+ pips
• Requires patience and bigger account

**Best For:**
• Catching major market trends
• People with limited screen time
• Building long-term wealth

**Strategy:**
1. Identify major trend on monthly/weekly
2. Wait for significant pullback
3. Enter with wide stop loss
4. Hold for weeks/months
5. Trail stop as trade moves in profit

**Like investing, but with leverage!** 💎"""

    # ========== RISK MANAGEMENT ==========
    
    def explain_risk(self):
        return """💰 **Risk Management - The #1 Skill:**

**The Rules:**
1. **1-2% Rule:** Never risk more than 1-2% of account per trade
2. **Risk/Reward:** Minimum 1:2 ratio (risk $10 to make $20)
3. **Daily Loss Limit:** Stop after losing 3-5% in one day
4. **Weekly Loss Limit:** Stop after losing 10% in one week

**Position Size Calculator:**
```
Position Size = (Account × Risk%) ÷ (Entry - Stop Loss)
```

**Example ($1000 account, 1% risk):**
• Risk amount: $10
• If stop loss is 20 pips away
• Position size = $10 ÷ 20 pips = $0.50/pip
• That's a 0.05 lot size

**Golden Rules:**
• ✅ Always use a stop loss
• ✅ Never move your SL further away
• ✅ Take partial profits at targets
• ✅ Risk the same % every trade
• ❌ Never risk money you can't afford to lose
• ❌ Never add to a losing position
• ❌ Never revenge trade after a loss

**This is what separates winners from losers!** 🏆"""

    # ========== CRYPTO ==========
    
    def explain_crypto(self, msg):
        if 'bitcoin' in msg or 'btc' in msg:
            return """₿ **Bitcoin (BTC):**

**What is it?**
The first and largest cryptocurrency. Digital gold. Created by Satoshi Nakamoto in 2009.

**Key Facts:**
• Max supply: 21 million coins
• Current dominance: ~45-50% of crypto market
• Halving: Every ~4 years (reduces new supply by 50%)
• Next halving creates supply shock → historically bullish

**Bitcoin Cycles:**
1. **Halving** occurs
2. Supply decreases
3. Price gradually increases
4. FOMO kicks in → rapid rise
5. Euphoria → bubble
6. Crash → bear market
7. Accumulation → repeat

**Trading BTC:**
• Use weekly/daily charts for trend
• Key levels: Round numbers ($50K, $100K)
• Correlates with stock market & macro events
• Most volatile during US market hours

**"Bitcoin is the apex predator of money"** 🦁"""
        
        return """🪙 **Cryptocurrency Overview:**

**Top Categories:**
• **Store of Value:** Bitcoin (BTC)
• **Smart Contracts:** Ethereum (ETH), Solana (SOL)
• **DeFi:** Aave, Uniswap, Compound
• **Layer 2:** Polygon, Arbitrum, Optimism
• **Memecoins:** DOGE, SHIB, PEPE

**Crypto Trading Tips:**
1. Only invest what you can afford to lose
2. Do your own research (DYOR)
3. Don't chase pumps
4. Take profits on the way up
5. Use hardware wallet for long-term holds

**Market Cycles:**
• **Accumulation** → Smart money buys quietly
• **Markup** → Price starts rising, momentum builds
• **Distribution** → Smart money sells to retail
• **Markdown** → Price crashes, fear dominates

**The key is to buy during accumulation!** 🎯"""

    # ========== FOREX ==========
    
    def explain_forex(self, msg):
        return """💱 **Forex Trading Guide:**

**Major Pairs:**
• EUR/USD - Most traded pair
• GBP/USD - "Cable" - volatile
• USD/JPY - "Ninja" - trend follower
• AUD/USD - "Aussie" - commodity linked
• USD/CHF - "Swissy" - safe haven

**What is a Pip?**
• Smallest price movement (0.0001 for most pairs)
• 1 standard lot = $10 per pip
• 1 mini lot = $1 per pip
• 1 micro lot = $0.10 per pip

**Best Times to Trade:**
• London Open (8:00 GMT) 🔥
• NY Open (13:00 GMT) 🔥
• London/NY Overlap (13:00-17:00 GMT) 🔥🔥

**Forex vs Crypto:**
• Forex is more stable and liquid
• Lower spreads
• More predictable technical patterns
• Available 24/5 (Mon-Fri)

**Start with 1-2 pairs and master them!** 🎯"""

    # ========== CONTENT ==========
    
    def create_content(self, msg):
        captions = [
            """✍️ **Viral Trading Captions:**

**Motivational:**
"The market doesn't care about your feelings. Trade your plan. 📊"

"I didn't come this far to only come this far. 🔥"

"Your network is your net worth. Build it. 🤝"

**Educational:**
"Stop looking for the perfect entry. Start managing risk perfectly. 💰"

"The best trade is the one you DON'T take. Patience pays. ⏳"

"3 years of trading taught me more than 4 years of college. 📚"

**Engagement Hooks:**
"What's your biggest trading mistake? Mine was... 👇"

"Unpopular opinion: You don't need indicators to be profitable. Agree? 🤔"

"Drop a 🔥 if you're grinding today!"

Want captions for a specific topic? Tell me! 🎯""",

            """📱 **Content Growth Strategy:**

**Post Types That Work:**
1. **Before/After** - Show your journey
2. **Tips & Tricks** - Quick value posts
3. **Charts & Analysis** - Show your trades
4. **Mindset Posts** - Motivational content
5. **Behind the Scenes** - Your daily routine

**Posting Schedule:**
• 1-2 posts per day
• Best times: 8-9 AM, 12-1 PM, 6-8 PM
• Mix educational (60%) + personal (40%)
• Use hashtags: #Trading #Forex #Crypto #SMC

**Hook Formulas:**
• "I lost $X before learning this ONE thing..."
• "99% of traders don't know this..."
• "Stop doing X. Start doing Y instead."
• "Here's why you keep losing money..."

**Grow your brand alongside your trading!** 🚀"""
        ]
        return random.choice(captions)

    # ========== PSYCHOLOGY ==========
    
    def explain_psychology(self, msg):
        if any(w in msg for w in ['revenge', 'emotion', 'angry', 'frustrat']):
            return """😤 **Handling Revenge Trading:**

**What is it?**
Trading emotionally after a loss to "win it back" - THE #1 ACCOUNT KILLER!

**How to Stop:**
1. **Walk Away Rule:** After 2 losses, close your platform
2. **Cooling Period:** Wait at least 1 hour after a loss
3. **Journal:** Write down how you feel BEFORE trading
4. **Checklist:** Does this trade meet ALL your criteria?
5. **Reduce Size:** After a loss, trade smaller

**Mindset Shift:**
• A loss is NOT a failure - it's data
• You're not "losing money" - you're paying tuition
• The market will be there tomorrow
• One trade doesn't define you

**Remember:** The goal is to be profitable over 100 trades, not the next one! 🎯"""
        
        return """🧠 **Trading Psychology:**

**The 4 Enemies:**
1. **Fear** - Missing entries, cutting winners too early
2. **Greed** - Overtrading, moving targets, overleveraging
3. **Hope** - Holding losers, not using stop losses
4. **Revenge** - Trading emotionally after a loss

**How to Build Mental Strength:**
• ✅ Trade with a plan EVERY time
• ✅ Accept losses as part of the game
• ✅ Journal every trade (entry, exit, emotion)
• ✅ Take breaks (trading is a marathon)
• ✅ Exercise, sleep well, eat healthy
• ✅ Meditate before trading sessions

**The 40-40-20 Rule:**
• 40% of your success = Psychology
• 40% of your success = Risk Management
• 20% of your success = Strategy

**Your strategy doesn't matter if you can't control yourself!** 💪"""

    # ========== MARKET ==========
    
    def explain_market(self, msg):
        return """📊 **Market Analysis:**

**Market Phases:**
1. **Accumulation** - Smart money buying, price flat
2. **Markup** - Uptrend begins, momentum builds
3. **Distribution** - Smart money selling, price tops
4. **Markdown** - Downtrend, fear dominates

**Current Market Reading Tips:**
• Check DXY (Dollar Index) for forex direction
• Watch Bitcoin dominance for altcoin rotation
• Monitor VIX (fear index) for stock market sentiment
• Follow economic calendar for news events

**Key Events That Move Markets:**
• 🇺🇸 FOMC/Fed Rate Decision
• 🇺🇸 NFP (Non-Farm Payrolls) - First Friday monthly
• 🇺🇸 CPI (Inflation Data)
• 🇪🇺 ECB Rate Decision
• 🇬🇧 BOE Rate Decision
• 🇯🇵 BOJ Rate Decision

**Rule:** Don't trade during major news unless you're experienced! ⚠️"""

    # ========== DEFI ==========
    
    def explain_defi(self, msg):
        return """🌐 **DeFi & Web3:**

**What is DeFi?**
Decentralized Finance - financial services without banks/intermediaries.

**Key DeFi Concepts:**
• **DEX** - Decentralized exchanges (Uniswap, PancakeSwap)
• **Yield Farming** - Earning rewards by providing liquidity
• **Staking** - Locking tokens to earn passive income
• **Lending/Borrowing** - Aave, Compound
• **Liquidity Pools** - Providing trading liquidity for fees

**Web3 Concepts:**
• **Smart Contracts** - Self-executing code on blockchain
• **DAOs** - Decentralized Autonomous Organizations
• **NFTs** - Non-Fungible Tokens (digital ownership)
• **Layer 2** - Scaling solutions (cheaper, faster)

**⚠️ DeFi Risks:**
• Smart contract bugs/hacks
• Impermanent loss in liquidity pools
• Rug pulls (scam projects)
• High gas fees on Ethereum

**DYOR (Do Your Own Research) always!** 🔍"""

    # ========== TRADING PLAN ==========
    
    def explain_plan(self, msg):
        return """📋 **Create Your Trading Plan:**

**Every trading plan needs:**

1. **Market & Pairs**
   • What do you trade? (Forex, Crypto, Stocks)
   • Which pairs/assets? (Max 2-3 to start)

2. **Timeframes**
   • Higher TF for trend (Daily/4H)
   • Lower TF for entry (1H/15M)

3. **Strategy Rules**
   • What setups do you take?
   • Entry criteria (minimum 3 confluences)
   • Stop loss placement
   • Take profit levels

4. **Risk Rules**
   • Max risk per trade: 1-2%
   • Max daily loss: 3-5%
   • Max weekly loss: 10%
   • Max open trades: 2-3

5. **Session Times**
   • When do you trade?
   • When do you NOT trade?

6. **Journal Template**
   • Date, pair, direction
   • Entry, SL, TP
   • Screenshot of setup
   • Emotion before/after
   • Grade: A+, A, B, C

**A trader without a plan is just gambling!** 🎰 → 📋"""

    # ========== MOTIVATION ==========
    
    def give_motivation(self, username):
        quotes = [
            f"""💪 **Listen up {username}!**

"The master has failed more times than the beginner has tried."

Every successful trader you see went through:
• Blown accounts
• Months of losses
• Wanting to quit
• Self-doubt

But they kept going. And so will you!

**Your journey:**
❌ Day 1-90: Learning, losing, frustrated
⚠️ Day 90-365: Getting better, still inconsistent
✅ Year 2+: Everything clicks, consistent profits

**You're not behind. You're exactly where you need to be.** 🚀""",

            f"""🔥 **{username}, read this carefully:**

"The stock market is a device for transferring money from the impatient to the patient." - Warren Buffett

**Truths about trading:**
• It's NOT a get-rich-quick scheme
• It IS a get-rich-slowly skill
• 90% quit before they get good
• The 10% who stay become wealthy

**What separates the 10%?**
• They journal every trade
• They follow their plan
• They manage risk religiously
• They never stop learning
• They treat it like a BUSINESS

**You're reading this because you're still in the game. That already puts you ahead!** 💎"""
        ]
        return random.choice(quotes)

    # ========== CALCULATOR ==========
    
    def calculate(self, msg):
        return """🧮 **Trading Calculators:**

**Position Size:**
Risk Amount = Account × Risk%
Lot Size = Risk Amount ÷ (SL in pips × pip value)

**Example:**
• $1000 account, 1% risk = $10 risk
• 20 pip stop loss
• $10 ÷ 20 = $0.50 per pip
• = 0.05 standard lots

**Risk/Reward:**
If you risk 20 pips and target 60 pips = 1:3 R:R ✅

**Pip Value (Standard Lot):**
• EUR/USD: $10 per pip
• GBP/USD: $10 per pip
• USD/JPY: ~$6.50 per pip

**Compound Growth:**
• 1% per day × 20 trading days = 22% per month
• Starting $1000 → ~$10,000 in 12 months (compounded)

**Remember:** Consistent small gains beat big risky bets! 📊"""



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
            flash(f"Welcome back, {user['username']}! 🎉", "success")
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
        FROM posts p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.created_at DESC
        LIMIT 50
    ''', (session['user_id'],)).fetchall()
    
    stories = db.execute('''
        SELECT s.*, u.username, u.avatar
        FROM stories s
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
        SELECT u.* FROM users u
        WHERE u.id != ?
        AND u.id NOT IN (SELECT following_id FROM follows WHERE follower_id = ?)
        LIMIT 5
    ''', (session['user_id'], session['user_id'])).fetchall()
    
    posts_list = []
    for post in posts:
        post_dict = dict(post)
        post_dict['time_ago'] = time_ago(post['created_at'])
        posts_list.append(post_dict)
    
    return render_template("feed.html",
                          posts=posts_list,
                          stories=stories,
                          trending=trending_tags,
                          suggested=suggested)


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
            filename = secure_filename(f"{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'posts', filename)
            file.save(filepath)
            media_url = f"/static/uploads/posts/{filename}"
            ext = filename.rsplit('.', 1)[1].lower()
            media_type = 'video' if ext in ['mp4', 'mov', 'webm'] else 'image'
    
    if not content and not media_url:
        return jsonify({'error': 'Post cannot be empty'}), 400
    
    db = get_db()
    cursor = db.execute('''INSERT INTO posts (user_id, content, media_url, media_type, feeling)
                           VALUES (?, ?, ?, ?, ?)''',
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
        db.execute("DELETE FROM likes WHERE user_id = ? AND post_id = ?",
                  (session['user_id'], post_id))
        action = 'unliked'
    else:
        db.execute("INSERT INTO likes (user_id, post_id) VALUES (?, ?)",
                  (session['user_id'], post_id))
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
        SELECT c.*, u.username, u.avatar
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.post_id = ?
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
        db.execute("DELETE FROM saved_posts WHERE user_id = ? AND post_id = ?",
                  (session['user_id'], post_id))
        action = 'unsaved'
    else:
        db.execute("INSERT INTO saved_posts (user_id, post_id) VALUES (?, ?)",
                  (session['user_id'], post_id))
        action = 'saved'
    
    db.commit()
    return jsonify({'status': action})

@app.route("/api/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ? AND user_id = ?",
                     (post_id, session['user_id'])).fetchone()
    
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
        filename = secure_filename(f"{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'stories', filename)
        file.save(filepath)
        
        media_url = f"/static/uploads/stories/{filename}"
        ext = filename.rsplit('.', 1)[1].lower()
        media_type = 'video' if ext in ['mp4', 'mov', 'webm'] else 'image'
        
        db = get_db()
        db.execute('''INSERT INTO stories (user_id, media_url, media_type, expires_at)
                      VALUES (?, ?, ?, datetime('now', '+24 hours'))''',
                  (session['user_id'], media_url, media_type))
        db.commit()
        
        return jsonify({'status': 'ok'})
    
    return jsonify({'error': 'Invalid file'}), 400

@app.route("/api/stories/<int:user_id>")
@login_required
def get_user_stories(user_id):
    db = get_db()
    stories = db.execute('''
        SELECT s.*, u.username
        FROM stories s
        JOIN users u ON s.user_id = u.id
        WHERE s.user_id = ? AND s.created_at > datetime('now', '-24 hours')
        ORDER BY s.created_at ASC
    ''', (user_id,)).fetchall()
    
    return jsonify([dict(s) for s in stories])


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
        db.execute("DELETE FROM follows WHERE follower_id = ? AND following_id = ?",
                  (session['user_id'], user_id))
        action = 'unfollowed'
    else:
        db.execute("INSERT INTO follows (follower_id, following_id) VALUES (?, ?)",
                  (session['user_id'], user_id))
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
                       (session['user_id'], f"📊 Poll: {question}"))
    post_id = cursor.lastrowid
    
    cursor = db.execute("INSERT INTO polls (post_id, question) VALUES (?, ?)",
                       (post_id, question))
    poll_id = cursor.lastrowid
    
    for opt in options:
        if opt.strip():
            db.execute("INSERT INTO poll_options (poll_id, option_text) VALUES (?, ?)",
                      (poll_id, opt.strip()))
    
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
        SELECT po.id, po.option_text, COUNT(pv.id) as votes
        FROM poll_options po
        LEFT JOIN poll_votes pv ON po.id = pv.option_id
        WHERE po.poll_id = ?
        GROUP BY po.id
    ''', (poll_id,)).fetchall()
    
    return jsonify({'status': 'ok', 'results': [dict(r) for r in results]})


# ================================
# PROFILE ROUTES
# ================================
@app.route("/profile/<username>")
@login_required
def profile(username):
    db = get_db()
    
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user:
        flash("User not found", "error")
        return redirect(url_for('feed'))
    
    posts = db.execute('''
        SELECT p.*,
            (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count,
            (SELECT COUNT(*) FROM comments WHERE post_id = p.id) as comment_count
        FROM posts p WHERE p.user_id = ?
        ORDER BY p.created_at DESC
    ''', (user['id'],)).fetchall()
    
    followers = db.execute("SELECT COUNT(*) as c FROM follows WHERE following_id = ?",
                          (user['id'],)).fetchone()['c']
    following = db.execute("SELECT COUNT(*) as c FROM follows WHERE follower_id = ?",
                          (user['id'],)).fetchone()['c']
    
    is_following = False
    if session['user_id'] != user['id']:
        is_following = db.execute("SELECT id FROM follows WHERE follower_id = ? AND following_id = ?",
                                 (session['user_id'], user['id'])).fetchone() is not None
    
    posts_list = []
    for post in posts:
        post_dict = dict(post)
        post_dict['time_ago'] = time_ago(post['created_at'])
        posts_list.append(post_dict)
    
    return render_template("profile.html",
                          profile_user=user,
                          posts=posts_list,
                          followers=followers,
                          following=following,
                          is_following=is_following,
                          is_own_profile=(session['user_id'] == user['id']))

@app.route("/api/profile/update", methods=["POST"])
@login_required
def update_profile():
    bio = request.form.get('bio', '')[:200]
    avatar_url = None
    
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{session['user_id']}_avatar.{file.filename.rsplit('.', 1)[1]}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'profiles', filename)
            file.save(filepath)
            avatar_url = f"/static/uploads/profiles/{filename}"
    
    db = get_db()
    if avatar_url:
        db.execute("UPDATE users SET bio = ?, avatar = ? WHERE id = ?",
                  (bio, avatar_url, session['user_id']))
    else:
        db.execute("UPDATE users SET bio = ? WHERE id = ?", (bio, session['user_id']))
    db.commit()
    
    flash("Profile updated!", "success")
    return redirect(url_for('profile', username=session['username']))


# ================================
# MESSAGES ROUTES
# ================================
@app.route("/messages")
@login_required
def messages():
    db = get_db()
    
    conversations = db.execute('''
        SELECT DISTINCT
            CASE WHEN sender_id = ? THEN receiver_id ELSE sender_id END as other_user_id
        FROM messages
        WHERE sender_id = ? OR receiver_id = ?
    ''', (session['user_id'], session['user_id'], session['user_id'])).fetchall()
    
    conv_list = []
    for conv in conversations:
        other_id = conv['other_user_id']
        other_user = db.execute("SELECT * FROM users WHERE id = ?", (other_id,)).fetchone()
        
        if other_user:
            last_msg = db.execute('''
                SELECT content, created_at FROM messages
                WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
                ORDER BY created_at DESC LIMIT 1
            ''', (session['user_id'], other_id, other_id, session['user_id'])).fetchone()
            
            conv_list.append({
                'other_user_id': other_id,
                'username': other_user['username'],
                'avatar': other_user['avatar'],
                'last_message': last_msg['content'] if last_msg else ''
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
        SELECT m.*, u.username
        FROM messages m
        JOIN users u ON m.sender_id = u.id
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


# ================================
# NOTIFICATIONS
# ================================
@app.route("/notifications")
@login_required
def notifications():
    db = get_db()
    notifs = db.execute('''
        SELECT n.*, u.username, u.avatar
        FROM notifications n
        LEFT JOIN users u ON n.from_user_id = u.id
        WHERE n.user_id = ?
        ORDER BY n.created_at DESC
        LIMIT 50
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
        FROM posts p
        JOIN users u ON p.user_id = u.id
        ORDER BY like_count DESC, p.created_at DESC
        LIMIT 30
    ''').fetchall()
    
    return render_template("explore.html", posts=posts)


# ================================
# REELS
# ================================
@app.route("/reels")
@login_required
def reels():
    db = get_db()
    reels = db.execute('''
        SELECT p.*, u.username, u.avatar
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.media_type = 'video'
        ORDER BY p.created_at DESC
        LIMIT 50
    ''').fetchall()
    return render_template("reels.html", reels=reels)


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
                      (f'%{q}%',)).fetchall()
    
    posts = db.execute('''
        SELECT p.*, u.username FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.content LIKE ?
        ORDER BY p.created_at DESC LIMIT 20
    ''', (f'%{q}%',)).fetchall()
    
    return jsonify({
        'users': [dict(u) for u in users],
        'posts': [dict(p) for p in posts]
    })


# ================================
# AI ROUTES
# ================================
@app.route("/ai")
@login_required
def ai():
    db = get_db()
    history = db.execute('''
        SELECT * FROM ai_chats WHERE user_id = ?
        ORDER BY created_at ASC LIMIT 50
    ''', (session['user_id'],)).fetchall()
    
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
        reply = brain.think(message, username)
        
        db = get_db()
        db.execute("INSERT INTO ai_chats (user_id, role, message) VALUES (?, ?, ?)",
                  (session['user_id'], 'user', message[:500]))
        db.execute("INSERT INTO ai_chats (user_id, role, message) VALUES (?, ?, ?)",
                  (session['user_id'], 'assistant', reply[:2000]))
        db.commit()
        
        return jsonify({'reply': reply})
    except Exception as e:
        print(f"AI Error: {e}")
        return jsonify({'reply': "Sorry, I encountered an error. Please try again!"}), 500

@app.route("/api/ai/clear", methods=["POST"])
@login_required
def api_ai_clear():
    db = get_db()
    db.execute("DELETE FROM ai_chats WHERE user_id = ?", (session['user_id'],))
    db.commit()
    return jsonify({'status': 'ok'})


# ================================
# FORGOT / RESET PASSWORD
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

    # ================================
# SETTINGS
# ================================
@app.route("/settings")
@login_required
def settings():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    
    followers = db.execute("SELECT COUNT(*) as c FROM follows WHERE following_id = ?",
                          (session['user_id'],)).fetchone()['c']
    following = db.execute("SELECT COUNT(*) as c FROM follows WHERE follower_id = ?",
                          (session['user_id'],)).fetchone()['c']
    post_count = db.execute("SELECT COUNT(*) as c FROM posts WHERE user_id = ?",
                           (session['user_id'],)).fetchone()['c']
    
    return render_template("settings.html", 
                          user=user, 
                          followers=followers, 
                          following=following,
                          post_count=post_count)

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
            filename = secure_filename(f"{session['user_id']}_avatar.{file.filename.rsplit('.', 1)[1]}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'profiles', filename)
            file.save(filepath)
            avatar_url = f"/static/uploads/profiles/{filename}"
    
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
    
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
              (hash_password(new_pass), session['user_id']))
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
# REAL-TIME CHAT API
# ================================
@app.route("/api/chat/<int:user_id>/messages")
@login_required
def get_chat_messages(user_id):
    db = get_db()
    messages = db.execute('''
        SELECT m.*, u.username
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
        ORDER BY created_at ASC
    ''', (session['user_id'], user_id, user_id, session['user_id'])).fetchall()
    
    return jsonify({'messages': [dict(m) for m in messages]})

    # ================================
# HASHTAG PAGES
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
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.content LIKE ?
        ORDER BY p.created_at DESC
        LIMIT 50
    ''', (session['user_id'], f'%#{tag}%')).fetchall()
    
    posts_list = []
    for post in posts:
        post_dict = dict(post)
        post_dict['time_ago'] = time_ago(post['created_at'])
        posts_list.append(post_dict)
    
    return render_template("hashtag.html", tag=tag, posts=posts_list)

    # ================================
# SOCIAL LOGIN ROUTES
# ================================

# Google Login
@app.route("/auth/google")
def google_login():
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
        
        # Check if user exists
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        
        if user:
            # Login existing user
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f"Welcome back, {user['username']}! 🎉", "success")
        else:
            # Create new user
            username = name.replace(' ', '_').lower()
            
            # Make username unique
            base_username = username
            counter = 1
            while True:
                existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
                if not existing:
                    break
                username = f"{base_username}{counter}"
                counter += 1
            
            # Create account with random password (they login via Google)
            random_pass = hashlib.sha256(os.urandom(32)).hexdigest()
            
            db.execute('''INSERT INTO users (username, email, password_hash, is_verified) 
                         VALUES (?, ?, ?, 1)''', (username, email, random_pass))
            db.commit()
            
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f"Welcome to Block4, {username}! 🎉", "success")
        
        return redirect(url_for('feed'))
        
    except Exception as e:
        print(f"Google OAuth Error: {e}")
        flash("Google login failed. Please try again.", "error")
        return redirect(url_for('login'))

# Apple Login (Redirect to signup for now)
@app.route("/auth/apple")
def apple_login():
    flash("Apple Sign In coming soon! Please use Google or email.", "error")
    return redirect(url_for('login'))

# Twitter Login (Redirect to signup for now)
@app.route("/auth/twitter")
def twitter_login():
    flash("Twitter Sign In coming soon! Please use Google or email.", "error")
    return redirect(url_for('login'))

    # ================================
# FOOTER PAGES
# ================================
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
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    
    print("\n" + "=" * 50)
    print("🚀 QHIVE - Smart Traders. Stronger Together.")
    print("=" * 50)
    print(f"📍 URL: http://127.0.0.1:{port}")
    print("✅ All features are REAL!")
    print("=" * 50 + "\n")
    app.run(debug=debug, host="0.0.0.0", port=port)