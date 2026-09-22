import os
import json
import logging
import time
import threading
import random
from datetime import datetime, timedelta
from flask import Flask, jsonify
import requests

TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 8080))
DATA_FILE = 'bonus_users.json'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === STORAGE ===
class Storage:
    def __init__(self, filename=DATA_FILE):
        self.filename = filename
        self.data = self._load_data()

    def _load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_data(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Save error: {e}")

    def get_user(self, user_id):
        if user_id not in self.data:
            self.data[user_id] = {
                'user_id': user_id,
                'points': 0,
                'total_earned': 0,
                'bonus_streak': 0,
                'last_daily': None,
                'last_bonus': None,
                'last_mega': None,
                'bonuses_claimed': 0,
                'daily_claimed': 0,
                'mega_claimed': 0,
                'username': '',
                'first_name': '',
                'last_name': '',
                'created_at': datetime.now().isoformat(),
                'last_active': datetime.now().isoformat()
            }
            self._save_data()
        return self.data[user_id]

    def save_user(self, user_id, data):
        self.data[user_id] = data
        self._save_data()

    def get_all_users(self):
        return self.data

storage = Storage()

# === TELEGRAM API ===
def send_message(chat_id, text, parse_mode='Markdown'):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }, timeout=10)
        if response.status_code == 200:
            logger.info(f"Message sent to {chat_id}")
        return response.json()
    except Exception as e:
        logger.error(f"Send message error: {e}")
        return None

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {'timeout': 30}
    if offset:
        params['offset'] = offset
    try:
        response = requests.get(url, params=params, timeout=35)
        if response.status_code == 200:
            return response.json().get('result', [])
        return []
    except Exception as e:
        logger.error(f"Get updates error: {e}")
        return []

def delete_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
    try:
        response = requests.get(url, timeout=10)
        logger.info(f"Webhook deleted: {response.json()}")
        return response.json().get('ok', False)
    except Exception as e:
        logger.error(f"Delete webhook error: {e}")
        return False

# === HELPERS ===
def get_time_until(iso_time, hours=24):
    if not iso_time:
        return "Available now!"
    try:
        last = datetime.fromisoformat(iso_time)
        next_time = last + timedelta(hours=hours)
        now = datetime.now()
        if now >= next_time:
            return "Available now!"
        diff = next_time - now
        h = diff.seconds // 3600
        m = (diff.seconds % 3600) // 60
        return f"{h}h {m}m"
    except:
        return "Available now!"

def get_streak_emoji(streak):
    if streak >= 100:
        return "👑"
    elif streak >= 50:
        return "💎"
    elif streak >= 30:
        return "🌟"
    elif streak >= 14:
        return "⭐"
    elif streak >= 7:
        return "🔥"
    return "💪"

def get_daily_bonus(streak):
    base = random.randint(10, 30)
    streak_bonus = (streak // 7) * 5
    return base + streak_bonus

def get_lucky_bonus():
    if random.random() < 0.1:
        return random.randint(50, 200), "JACKPOT"
    elif random.random() < 0.3:
        return random.randint(25, 50), "BIG"
    else:
        return random.randint(5, 25), "NORMAL"

# === COMMANDS ===
def handle_start(chat_id, user_data):
    user_id = str(chat_id)
    user = storage.get_user(user_id)
    user['username'] = user_data.get('username', '')
    user['first_name'] = user_data.get('first_name', 'User')
    user['last_name'] = user_data.get('last_name', '')
    user['last_active'] = datetime.now().isoformat()
    storage.save_user(user_id, user)
    
    welcome = f"""
🎁 *WELCOME TO VIP BONUS!*

👋 *Hello {user['first_name']}!*

💰 *Points: {user['points']}*
📅 *Bonus Streak: {user['bonus_streak']} days*
🎯 *Bonuses Claimed: {user.get('bonuses_claimed', 0)}*

📋 *Available Commands:*
/daily - Claim daily bonus 📅
/bonus - Claim lucky bonus 🎰
/mega - Claim mega bonus 💎
/claim - Collect all rewards 💰
/profile - View your profile 👤
/leaderboard - Top players 🏆
/help - All commands 📚

🔥 *VIP Bonus Benefits:*
• Daily bonuses (10-30+ points)
• Lucky bonuses (5-200 points)
• Mega bonuses (100-500 points)
• Streak multipliers

*Use /daily to claim your first bonus!*
    """
    send_message(chat_id, welcome)

def handle_help(chat_id):
    help_text = """
📚 *VIP BONUS COMMANDS*
━━━━━━━━━━━━━━━━

🎁 *Bonus Commands:*
/daily - Daily bonus (24h)
/bonus - Lucky bonus (12h)
/mega - Mega bonus (48h)
/claim - Collect rewards

📊 *Info Commands:*
/profile - View profile
/leaderboard - Top players
/help - This menu

💰 *Bonus Types:*
• Daily: 10-30+ points
• Lucky: 5-200 points (jackpot chance!)
• Mega: 100-500 points

⭐ *Streak Bonuses:*
• 7 days: +5 bonus
• 14 days: +10 bonus
• 30 days: +20 bonus
• 50 days: +30 bonus
• 100 days: +50 bonus

🎯 *Earn bonuses every day!*
    """
    send_message(chat_id, help_text)

def handle_daily(chat_id):
    user_id = str(chat_id)
    user = storage.get_user(user_id)
    now = datetime.now()
    
    if user.get('last_daily'):
        try:
            last = datetime.fromisoformat(user['last_daily'])
            if now - last < timedelta(hours=24):
                time_left = get_time_until(user['last_daily'])
                send_message(
                    chat_id,
                    f"""
⏳ *Daily Bonus Already Claimed!*
━━━━━━━━━━━━━━━━
🕐 Next in: {time_left}

📅 Bonus Streak: {user['bonus_streak']} days
💪 Keep your streak going!
                    """
                )
                return
        except:
            pass
    
    # Update streak
    if user.get('last_daily'):
        try:
            last = datetime.fromisoformat(user['last_daily'])
            if now - last < timedelta(hours=48):
                user['bonus_streak'] += 1
            else:
                user['bonus_streak'] = 1
        except:
            user['bonus_streak'] = 1
    else:
        user['bonus_streak'] = 1
    
    reward = get_daily_bonus(user['bonus_streak'])
    
    user['points'] += reward
    user['total_earned'] = user.get('total_earned', 0) + reward
    user['bonuses_claimed'] = user.get('bonuses_claimed', 0) + 1
    user['daily_claimed'] = user.get('daily_claimed', 0) + 1
    user['last_daily'] = now.isoformat()
    storage.save_user(user_id, user)
    
    emoji = get_streak_emoji(user['bonus_streak'])
    
    message = "🎉 *Daily Bonus Claimed!*"
    if user['bonus_streak'] == 1:
        message = "🌱 *First bonus claimed! Welcome!*"
    elif user['bonus_streak'] == 7:
        message = "🔥 *7-Day Streak! On fire!*"
    elif user['bonus_streak'] == 30:
        message = "🌟 *30-Day Streak! Legendary!*"
    elif user['bonus_streak'] == 100:
        message = "👑 *100-Day Streak! Ultimate!*"
    
    send_message(
        chat_id,
        f"""
{message}
━━━━━━━━━━━━━━━━
{emoji} *+{reward} points*
📅 *Streak: {user['bonus_streak']} days*
💰 *Total: {user['points']} points*

Come back tomorrow! 🚀
        """
    )

def handle_bonus(chat_id):
    user_id = str(chat_id)
    user = storage.get_user(user_id)
    now = datetime.now()
    
    if user.get('last_bonus'):
        try:
            last = datetime.fromisoformat(user['last_bonus'])
            if now - last < timedelta(hours=12):
                time_left = get_time_until(user['last_bonus'], 12)
                send_message(
                    chat_id,
                    f"""
⏳ *Lucky Bonus Already Claimed!*
━━━━━━━━━━━━━━━━
🕐 Next in: {time_left}

💡 Lucky bonus can give up to 200 points!
                    """
                )
                return
        except:
            pass
    
    amount, bonus_type = get_lucky_bonus()
    
    user['points'] += amount
    user['total_earned'] = user.get('total_earned', 0) + amount
    user['bonuses_claimed'] = user.get('bonuses_claimed', 0) + 1
    user['last_bonus'] = now.isoformat()
    storage.save_user(user_id, user)
    
    if bonus_type == "JACKPOT":
        message = "🎊 *JACKPOT!* Amazing luck!"
    elif bonus_type == "BIG":
        message = "🎉 *Big Bonus!* Great win!"
    else:
        message = "🎰 *Lucky Bonus Claimed!*"
    
    send_message(
        chat_id,
        f"""
{message}
━━━━━━━━━━━━━━━━
💰 *+{amount} points*
💵 *Total: {user['points']} points*

Come back in 12 hours! 🎯
        """
    )

def handle_mega(chat_id):
    user_id = str(chat_id)
    user = storage.get_user(user_id)
    now = datetime.now()
    
    if user.get('last_mega'):
        try:
            last = datetime.fromisoformat(user['last_mega'])
            if now - last < timedelta(hours=48):
                time_left = get_time_until(user['last_mega'], 48)
                send_message(
                    chat_id,
                    f"""
⏳ *Mega Bonus Already Claimed!*
━━━━━━━━━━━━━━━━
🕐 Next in: {time_left}

💎 Mega bonus gives 100-500 points!
                    """
                )
                return
        except:
            pass
    
    reward = random.randint(100, 500)
    
    user['points'] += reward
    user['total_earned'] = user.get('total_earned', 0) + reward
    user['bonuses_claimed'] = user.get('bonuses_claimed', 0) + 1
    user['mega_claimed'] = user.get('mega_claimed', 0) + 1
    user['last_mega'] = now.isoformat()
    storage.save_user(user_id, user)
    
    send_message(
        chat_id,
        f"""
💎 *MEGA BONUS CLAIMED!*
━━━━━━━━━━━━━━━━
💰 *+{reward} points*
🎯 *Mega Claims: {user['mega_claimed']}*
💵 *Total: {user['points']} points*

Come back in 48 hours! 🚀
        """
    )

def handle_claim(chat_id):
    user_id = str(chat_id)
    user = storage.get_user(user_id)
    
    bonus = random.randint(5, 25)
    user['points'] += bonus
    user['total_earned'] = user.get('total_earned', 0) + bonus
    storage.save_user(user_id, user)
    
    send_message(
        chat_id,
        f"""
✨ *Collection Bonus!*
━━━━━━━━━━━━━━━━
🎁 *+{bonus} points*
💵 *Total: {user['points']} points*

Keep collecting! 🚀
        """
    )

def handle_profile(chat_id):
    user_id = str(chat_id)
    user = storage.get_user(user_id)
    emoji = get_streak_emoji(user['bonus_streak'])
    
    all_users = storage.get_all_users()
    sorted_users = sorted(
        [(uid, data) for uid, data in all_users.items()],
        key=lambda x: x[1].get('points', 0),
        reverse=True
    )
    
    rank = 1
    for i, (uid, data) in enumerate(sorted_users, 1):
        if uid == user_id:
            rank = i
            break
    
    send_message(
        chat_id,
        f"""
👤 *YOUR PROFILE*
━━━━━━━━━━━━━━━━

👤 *Name:* {user.get('first_name', 'User')}
📛 *Username:* @{user.get('username', 'N/A')}

💰 *Points: {user['points']}*
⭐ *Total Earned: {user.get('total_earned', 0)}*
📅 *Streak: {user['bonus_streak']} days {emoji}*
🎯 *Bonuses Claimed: {user.get('bonuses_claimed', 0)}*
📊 *Daily Claims: {user.get('daily_claimed', 0)}*
💎 *Mega Claims: {user.get('mega_claimed', 0)}*
🏆 *Rank: #{rank} of {len(sorted_users)}*
        """
    )

def handle_leaderboard(chat_id):
    all_users = storage.get_all_users()
    sorted_users = sorted(
        [(uid, data) for uid, data in all_users.items()],
        key=lambda x: x[1].get('points', 0),
        reverse=True
    )[:10]
    
    if not sorted_users:
        send_message(chat_id, "No users yet! Be the first! 🏆")
        return
    
    message = "🏆 *VIP BONUS LEADERBOARD*\n━━━━━━━━━━━━━━━━\n\n"
    for i, (uid, data) in enumerate(sorted_users, 1):
        medal = '🥇' if i == 1 else '🥈' if i == 2 else '🥉' if i == 3 else f"{i}."
        name = data.get('username', data.get('first_name', f"User{uid}"))
        points = data.get('points', 0)
        streak = data.get('bonus_streak', 0)
        emoji = get_streak_emoji(streak)
        message += f"{medal} @{name} - {points} pts {emoji}\n"
    
    send_message(chat_id, message)

# === POLLING ===
def process_updates():
    last_update_id = 0
    logger.info("Starting polling loop...")
    
    delete_webhook()
    
    while True:
        try:
            updates = get_updates(last_update_id + 1 if last_update_id else None)
            
            for update in updates:
                update_id = update.get('update_id')
                if update_id:
                    last_update_id = update_id
                
                if 'message' in update:
                    msg = update['message']
                    chat_id = msg['chat']['id']
                    user_data = msg.get('from', {})
                    
                    if 'text' in msg:
                        text = msg['text']
                        logger.info(f"Command from {chat_id}: {text}")
                        
                        if text.startswith('/start'):
                            handle_start(chat_id, user_data)
                        elif text.startswith('/help'):
                            handle_help(chat_id)
                        elif text.startswith('/daily'):
                            handle_daily(chat_id)
                        elif text.startswith('/bonus'):
                            handle_bonus(chat_id)
                        elif text.startswith('/mega'):
                            handle_mega(chat_id)
                        elif text.startswith('/claim'):
                            handle_claim(chat_id)
                        elif text.startswith('/profile'):
                            handle_profile(chat_id)
                        elif text.startswith('/leaderboard'):
                            handle_leaderboard(chat_id)
                        else:
                            send_message(
                                chat_id,
                                "❓ Unknown command. Use /help to see available commands."
                            )
            
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Process updates error: {e}")
            time.sleep(5)

# === FLASK ===
app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    all_users = storage.get_all_users()
    total_bonuses = sum(data.get('bonuses_claimed', 0) for data in all_users.values())
    
    return f"""
    <h1>🎁 VIP Bonus Bot</h1>
    <p>Bot is running!</p>
    <p>Users: {len(all_users)}</p>
    <p>Total Bonuses Claimed: {total_bonuses}</p>
    <p>Status: ✅ Active</p>
    <p>Bot: @VIP_3Bonusbot</p>
    """

@app.route('/stats', methods=['GET'])
def stats_route():
    all_users = storage.get_all_users()
    return jsonify({
        'users': len(all_users),
        'total_bonuses': sum(data.get('bonuses_claimed', 0) for data in all_users.values()),
        'total_daily': sum(data.get('daily_claimed', 0) for data in all_users.values()),
        'total_mega': sum(data.get('mega_claimed', 0) for data in all_users.values()),
        'total_points': sum(data.get('points', 0) for data in all_users.values())
    })

# === MAIN ===
def main():
    logger.info("=" * 50)
    logger.info("Starting VIP Bonus Bot...")
    logger.info("Bot: @VIP_3Bonusbot")
    logger.info(f"Data File: {DATA_FILE}")
    logger.info("=" * 50)
    
    poll_thread = threading.Thread(target=process_updates, daemon=True)
    poll_thread.start()
    logger.info("Polling thread started")
    
    logger.info(f"Starting Flask server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    main()
