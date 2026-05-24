import telebot
import requests
import hashlib
import time
import json
import os
import threading
import random
from telebot import types
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from supabase import create_client, Client

# --- CONFIGURATION ---
API_TOKEN = '8469731551:AAGd9fP3FyD5jk7yXmhPqIhdPdDFoz4pXJA'
ADMIN_ID = 6232671662 
PAYMENT_BOT_USER = "SimpleTask_KeyBot" 

BASE_URL = "https://admin.simpletasks88.com"
VERIFY_SALT = "yh123456"

SUPABASE_URL = "https://hbqdrjyjooojzsqadixa.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhicWRyanlqb29vanpzcWFkaXhhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk1NTE5NTMsImV4cCI6MjA5NTEyNzk1M30.H5YHcwP3lVr0vKPG19L17gwy_e68ehXvDUaKlYpv924"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(API_TOKEN)
user_sessions = {} 
add_num_state = {}

# --- LITE CLOUD DB ENGINE ---
def check_sub(uid):
    if int(uid) == int(ADMIN_ID): 
        return True
    try:
        res = supabase.table("users").select("expiry").eq("uid", str(uid)).execute()
        if res.data and len(res.data) > 0:
            expiry = res.data[0].get("expiry")
            if not expiry: return False
            return datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S") > datetime.now()
        return False
    except Exception as e:
        print(f"Sub check error: {e}")
        return False

def load_st_sessions():
    global user_sessions
    try:
        res = supabase.table("sessions").select("*").execute()
        if res.data:
            for d in res.data:
                cid = int(d['cid'])
                user_sessions[cid] = SimpleTaskAPI(d['t'], d['u'], d['un'])
    except Exception as e:
        print(f"Load sessions error: {e}")

def save_st_sessions():
    try:
        for k, v in user_sessions.items():
            supabase.table("sessions").upsert({
                "cid": str(k), "t": str(v.token), "u": str(v.userid), "un": str(v.username)
            }).execute()
    except Exception as e:
        print(f"Save sessions error: {e}")

def get_md5(data): return hashlib.md5(data.encode()).hexdigest()

# --- API CLASS ---
class SimpleTaskAPI:
    def __init__(self, t, uid, un):
        self.token, self.userid, self.username = str(t), str(uid), str(un)

    def get_headers(self, auth=True):
        ts = str(int(time.time() * 1000))
        h = {
            "verify-time": ts,
            "verify-encrypt": get_md5(VERIFY_SALT + ts),
            "Businessid": "1",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        }
        if auth: h["Authorization"] = self.token
        return h

    def login(self, u, p):
        endpoint = "/api/user/login"
        pw = get_md5(get_md5(p)).lower()
        sign = get_md5(get_md5(endpoint) + f"{u}{pw}")
        try:
            r = requests.post(f"{BASE_URL}{endpoint}", json={"username": u, "userpwd": pw, "sign": sign}, headers=self.get_headers(False), timeout=15).json()
            if r.get("code") == 0:
                self.token, self.userid, self.username = str(r.get("token")), str(r['data']['info']['id']), str(r['data']['info']['account'])
                return True, r['data']['info']
            return False, r.get("message")
        except Exception as e: return False, str(e)

    def get_info(self):
        endpoint = "/api/user/get_appinfo"
        sign = get_md5(get_md5(endpoint) + self.userid + self.username)
        try:
            r = requests.get(f"{BASE_URL}{endpoint}", params={"userid": self.userid, "username": self.username, "sign": sign}, headers=self.get_headers(), timeout=10).json()
            return r if r.get("code") == 0 else None
        except: return None

    def hit(self, p, wsid):
        endpoint = "/api/user/sendmsg"
        sign = get_md5(get_md5(endpoint) + f"{p}{wsid}" + self.userid + self.username)
        try: return requests.post(f"{BASE_URL}{endpoint}", json={"phone": p, "wsid": int(wsid), "username": self.username, "userid": int(self.userid), "sign": sign}, headers=self.get_headers(), timeout=15).json()
        except: return {"code": -1}

# --- HANDLERS ---
@bot.message_handler(commands=['start'])
def start(m):
    cid, uid = m.chat.id, str(m.chat.id)
    bot.clear_step_handler_by_chat_id(cid)
    
    try:
        supabase.table("users").upsert({"uid": uid, "name": str(m.from_user.first_name)}).execute()
    except Exception as e:
        print(f"User upsert error: {e}")

    if not check_sub(uid):
        kb = types.InlineKeyboardMarkup(); kb.add(types.InlineKeyboardButton("Subscription 💳", url=f"https://t.me/{PAYMENT_BOT_USER}"))
        return bot.send_message(cid, f"🚀 **Simple Task 4x**\n\nYour access is expired. Please buy a subscription to continue.", reply_markup=kb, parse_mode="HTML")

    if cid not in user_sessions:
        kb = types.InlineKeyboardMarkup(); kb.add(types.InlineKeyboardButton("Sync Dashboard 🔐", callback_data="login_v38"))
        return bot.send_message(cid, "✅ **Premium Active!**\nPlease login to sync your account:", reply_markup=kb, parse_mode="HTML")

    show_menu(cid)

def show_menu(cid):
    kb = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.add("📊 Dashboard", "➕ Add Number")
    kb.add("🚀 Send All SMS", "👤 My Account")
    kb.add("🆘 Help", "🚪 Logout")
    if int(cid) == int(ADMIN_ID): kb.add("🛠️ Admin Panel")
    bot.send_message(cid, "🏠 **Main Menu**", reply_markup=kb, parse_mode="HTML")

# --- LOGIN FLOW ---
@bot.callback_query_handler(func=lambda c: c.data == "login_v38")
def login_init(c):
    msg = bot.send_message(c.message.chat.id, "👤 Enter SimpleTask **Username**:", parse_mode="HTML")
    bot.register_next_step_handler(msg, lgn_u)

def lgn_u(m):
    if m.text == "/start": return start(m)
    add_num_state[m.chat.id] = {"tmp_u": m.text.strip()}
    msg = bot.send_message(m.chat.id, "🔑 Enter SimpleTask **Password**:", parse_mode="HTML")
    bot.register_next_step_handler(msg, lgn_p)

def lgn_p(m):
    cid = m.chat.id; api = SimpleTaskAPI("", "", "")
    if cid not in add_num_state: return start(m)
    ok, res = api.login(add_num_state[cid]["tmp_u"], m.text.strip())
    if ok:
        user_sessions[cid] = api; save_st_sessions()
        bot.send_message(cid, "✅ **Login Successful!** Dashboard ready.")
        show_menu(cid)
    else: bot.send_message(cid, f"❌ **Failed:** {res}")

# --- DASHBOARD & MISSION ---
@bot.message_handler(func=lambda m: m.text == "📊 Dashboard")
def dashboard(m):
    if not check_sub(m.chat.id): return start(m)
    api = user_sessions.get(m.chat.id)
    if not api: return login_init(m)
    
    bot.send_chat_action(m.chat.id, 'typing')
    res = api.get_info()
    if not res: return bot.send_message(m.chat.id, "❌ Server connection error.")
    
    online = [i for i in res.get('data', {}).get('list', []) if i.get('isonline') == 1]
    
    txt = f"📊 **Live Overview**\n"
    txt += f"Active Numbers: <b>{len(online)}</b>\n"
    txt += f"----------------------------\n"
    if online:
        for idx, i in enumerate(online, 1):
            cnt = i.get('msgcount', 0)
            txt += f"{idx}. 📲 <code>{i.get('wsnumber')}</code> | 📤 <b>{cnt}</b>\n"
    else: txt += "⚠️ No online numbers found."
    bot.send_message(m.chat.id, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "➕ Add Number")
def add_num_start(m):
    if not check_sub(m.chat.id): return
    msg = bot.send_message(m.chat.id, "📱 Enter: `CC Number` (e.g. `880 1712345678`)", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_add)

def process_add(m):
    try:
        parts = m.text.split(); cc, num = parts[0], parts[1]
        api = user_sessions.get(m.chat.id)
        if not api: return bot.send_message(m.chat.id, "Login required.")
        get_code_logic(m.chat.id, api, cc, num, 0)
    except: bot.send_message(m.chat.id, "❌ Format error. Example: `880 1712345678`")

def get_code_logic(cid, api, cc, num, z):
    full = f"{cc}{'0'*z}{num}"
    endpoint = "/api/user/get_code"
    sign = get_md5(get_md5(endpoint) + full + api.userid + api.username)
    try:
        r = requests.get(f"{BASE_URL}{endpoint}", params={"account":full,"signType":"1","username":api.username,"userid":api.userid,"sign":sign}, headers=api.get_headers(), timeout=10).json()
        if r.get("code") == 0:
            kb = types.InlineKeyboardMarkup(); kb.add(types.InlineKeyboardButton("Next Variation ➡️", callback_data="var_nxt"))
            bot.send_message(cid, f"📱 Number: <code>{full}</code>\n🔑 Pairing Code: <code>{r.get('data')}</code>", reply_markup=kb, parse_mode="HTML")
            add_num_state[cid] = {"api": api, "cc": cc, "num": num, "z": z+1}
            threading.Thread(target=watch_v38, args=(cid, api, full)).start()
        else: bot.send_message(cid, f"❌ Error: {r.get('message')}")
    except: bot.send_message(cid, "❌ Timeout.")

@bot.callback_query_handler(func=lambda c: c.data == "var_nxt")
def variation_nxt(c):
    s = add_num_state.get(c.message.chat.id)
    if s: get_code_logic(c.message.chat.id, s['api'], s['cc'], s['num'], s['z'])

def watch_v38(cid, api, target):
    for _ in range(30):
        time.sleep(45)
        res = api.get_info()
        if res:
            for i in res.get('data', {}).get('list', []):
                if str(i.get('wsnumber')) in str(target) and i.get('isonline') == 1:
                    bot.send_message(cid, f"✅ **Account Online!**\n<code>{target}</code> is ready.", parse_mode="HTML")
                    return

@bot.message_handler(func=lambda m: m.text == "🚀 Send All SMS")
def mission_v38(m):
    cid = m.chat.id; api = user_sessions.get(cid)
    if not check_sub(cid) or not api: return
    
    res = api.get_info()
    on = [i for i in res.get('data', {}).get('list', []) if i.get('isonline') == 1]
    if not on: return bot.send_message(cid, "❌ No online numbers.")
    
    status_msg = bot.send_message(cid, "🚀 **Sending SMS please wait...**", parse_mode="HTML")
    
    success = 0
    with ThreadPoolExecutor(max_workers=50) as ex:
        results = list(ex.map(lambda x: api.hit(x['wsnumber'], x['id']), on))
    
    for r in results:
        if r.get('code') == 0: success += 1
    
    bot.edit_message_text(f"🏁 **Mission Finished!**\nSuccess: <code>{success}/{len(on)}</code>", cid, status_msg.message_id, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "👤 My Account")
def btn_account(m):
    cid = m.chat.id; s = user_sessions.get(cid)
    exp = "No Sub"
    try:
        res = supabase.table("users").select("*").eq("uid", str(cid)).execute()
        if res.data and len(res.data) > 0:
            exp = res.data[0].get("expiry", "No Sub")
            if not exp: exp = "No Sub"
    except: pass
    
    pts = "Sync Required"
    if s:
        endpoint = "/api/user/get_userbalance"
        sign = get_md5(get_md5(endpoint) + s.userid + s.username)
        try:
            r = requests.get(f"{BASE_URL}{endpoint}", params={"username":s.username,"userid":s.userid,"sign":sign}, headers=s.get_headers()).json()
            pts = f"{r.get('data', '0')} Points"
        except: pts = "Error"

    txt = f"👤 **Account Overview**\nBalance: <b>{pts}</b>\nExpiry: <b>{exp}</b>"
    bot.send_message(cid, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🚪 Logout")
def logout(m):
    user_sessions.pop(m.chat.id, None)
    try: supabase.table("sessions").delete().eq("cid", str(m.chat.id)).execute()
    except: pass
    bot.send_message(m.chat.id, "Logged Out.", reply_markup=types.ReplyKeyboardRemove())

# --- ADMIN PANEL ---
@bot.message_handler(func=lambda m: m.text == "🛠️ Admin Panel" and int(m.chat.id) == int(ADMIN_ID))
def admin_p(m):
    kb = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.add("📢 Broadcast", "➕ Manual Access", "🔙 Back")
    bot.send_message(m.chat.id, "🛡️ **V38 Administration**", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast" and int(m.chat.id) == int(ADMIN_ID))
def broadcast_step1(m):
    msg = bot.send_message(m.chat.id, "📝 Enter the message to broadcast to all users:")
    bot.register_next_step_handler(msg, do_broadcast)

def do_broadcast(m):
    count = 0
    try:
        res = supabase.table("users").select("uid").execute()
        if res.data:
            for u in res.data:
                try:
                    bot.send_message(u['uid'], f"📢 **ADMIN BROADCAST**\n\n{m.text}", parse_mode="HTML")
                    count += 1
                except: pass
    except: pass
    bot.send_message(ADMIN_ID, f"✅ Broadcast finished. Sent to {count} users.")

@bot.message_handler(func=lambda m: m.text == "➕ Manual Access" and int(m.chat.id) == int(ADMIN_ID))
def manual_acc(m):
    msg = bot.send_message(m.chat.id, "Enter `ID Days` (e.g. `123456 30`):")
    bot.register_next_step_handler(msg, do_manual)

def do_manual(m):
    try:
        parts = m.text.split()
        if len(parts) != 2: raise Exception("Invalid format")
        uid, days = parts[0], parts[1]
        exp = (datetime.now() + timedelta(days=int(days))).strftime("%Y-%m-%d %H:%M:%S")
        
        supabase.table("users").upsert({"uid": str(uid), "name": "Manual", "expiry": exp}).execute()
        bot.send_message(m.chat.id, f"✅ Access granted to {uid}.")
        try: bot.send_message(int(uid), f"🎉 Admin has granted you **{days} Days** access!", parse_mode="HTML")
        except: pass
    except Exception as e: 
        bot.send_message(m.chat.id, f"❌ Error: {str(e)}")

@bot.message_handler(func=lambda m: m.text == "🔙 Back")
def back_to_menu(m):
    show_menu(m.chat.id)

@bot.message_handler(func=lambda m: m.reply_to_message and int(m.chat.id) == int(ADMIN_ID))
def admin_reply(m):
    try:
        target = m.reply_to_message.text.split("USERID:")[1].split("\n")[0].strip()
        bot.send_message(int(target), f"✉️ **Admin Response:**\n\n{m.text}", parse_mode="HTML")
        bot.reply_to(m, "✅ Delivered.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "🆘 Help")
def help_v38(m):
    msg = bot.send_message(m.chat.id, "🆘 **Describe issue:**")
    bot.register_next_step_handler(msg, lambda ms: bot.send_message(ADMIN_ID, f"🆘 **HELP REQUEST**\nUSERID:{ms.chat.id}\n\nMsg: {ms.text}"))

if __name__ == "__main__":
    load_st_sessions()
    print("🤖 Main Bot V38 (Simple Task 4x) Online...")
    while True:
        try: bot.polling(none_stop=True, timeout=90)
        except: time.sleep(5)
    
