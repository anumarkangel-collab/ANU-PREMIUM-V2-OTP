import os
import logging
import asyncio
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from supabase import create_client, Client

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Initialize Supabase Client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Import all endpoints from zenex_api.py
from zenex_api import (
    provision_virtual_number,
    fetch_sms_payloads,
    fetch_active_ranges,
    fetch_global_broadcast
)

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# OTP Channel / Group Chat ID and Public Link
OTP_GROUP_CHAT_ID = "-1004360371933"
OTP_CHANNEL_URL = "https://t.me/anupremiumotpchannel"

# Dictionary to track active numbers per user: {user_id: [number1, number2, number3]}
USER_ACTIVE_NUMBERS = {}

# Track already processed SMS IDs (nid) to avoid duplicate notifications
PROCESSED_NIDS = set()

# Comprehensive country name and prefix flag lookup map (expanded with all countries)
COUNTRY_FLAG_MAP = {
    # Africa
    "algeria": "🇩🇿", "213": "🇩🇿",
    "angola": "🇦🇴", "244": "🇦🇴",
    "benin": "🇧🇯", "229": "🇧🇯",
    "botswana": "🇧🇼", "267": "🇧🇼",
    "burkina faso": "🇧🇫", "226": "🇧🇫",
    "burundi": "🇧🇮", "257": "🇧🇮",
    "cameroon": "🇨🇲", "237": "🇨🇲",
    "cape verde": "🇨🇻", "238": "🇨🇻",
    "central african republic": "🇨🇫", "236": "🇨🇫",
    "chad": "🇹🇩", "235": "🇹🇩",
    "comoros": "🇰🇲", "269": "🇰🇲",
    "congo": "🇨🇬", "242": "🇨🇬",
    "djibouti": "🇩🇯", "253": "🇩🇯",
    "egypt": "🇪🇬", "20": "🇪🇬",
    "equatorial guinea": "🇬🇶", "240": "🇬🇶",
    "eritrea": "🇪🇷", "291": "🇪🇷",
    "eswatini": "🇸🇿", "268": "🇸🇿",
    "ethiopia": "🇪🇹", "251": "🇪🇹",
    "gabon": "🇬🇦", "241": "🇬🇦",
    "gambia": "🇬🇲", "220": "🇬🇲",
    "ghana": "🇬🇭", "233": "🇬🇭",
    "guinea": "🇬🇳", "224": "🇬🇳",
    "guinea-bissau": "🇬🇼", "245": "🇬🇼",
    "ivory coast": "🇨🇮", "cote d'ivoire": "🇨🇮", "225": "🇨🇮",
    "kenya": "🇰🇪", "254": "🇰🇪",
    "lesotho": "🇱🇸", "266": "🇱🇸",
    "liberia": "🇱🇷", "231": "🇱🇷",
    "libya": "🇱🇾", "218": "🇱🇾",
    "madagascar": "🇲🇬", "261": "🇲🇬",
    "malawi": "🇲🇼", "265": "🇲🇼",
    "mali": "🇲🇱", "223": "🇲🇱",
    "mauritania": "🇲🇷", "222": "🇲🇷",
    "mauritius": "🇲🇺", "230": "🇲🇺",
    "morocco": "🇲🇦", "212": "🇲🇦",
    "mozambique": "🇲🇿", "258": "🇲🇿",
    "namibia": "🇳🇦", "264": "🇳🇦",
    "niger": "🇳🇪", "227": "🇳🇪",
    "nigeria": "🇳🇬", "234": "🇳🇬",
    "rwanda": "🇷🇼", "250": "🇷🇼",
    "sao tome and principe": "🇸🇹", "239": "🇸🇹",
    "senegal": "🇸🇳", "221": "🇸🇳",
    "seychelles": "🇸🇨", "248": "🇸🇨",
    "sierra leone": "🇸🇱", "232": "🇸🇱",
    "somalia": "🇸🇴", "252": "🇸🇴",
    "south africa": "🇿🇦", "27": "🇿🇦",
    "south sudan": "🇸🇸", "211": "🇸🇸",
    "sudan": "🇸🇩", "249": "🇸🇩",
    "tanzania": "🇹🇿", "255": "🇹🇿",
    "togo": "🇹🇬", "228": "🇹🇬",
    "tunisia": "🇹🇳", "216": "🇹🇳",
    "uganda": "🇺🇬", "256": "🇺🇬",
    "zambia": "🇿🇲", "260": "🇿🇲",
    "zimbabwe": "🇿🇼", "263": "🇿🇼",

    # Asia & Middle East
    "afghanistan": "🇦🇫", "93": "🇦🇫",
    "armenia": "🇦🇲", "374": "🇦🇲",
    "azerbaijan": "🇦🇿", "994": "🇦🇿",
    "bahrain": "🇧🇭", "973": "🇧🇭",
    "bangladesh": "🇧🇩", "880": "🇧🇩",
    "bhutan": "🇧🇹", "975": "🇧🇹",
    "brunei": "🇧🇳", "673": "🇧🇳",
    "cambodia": "🇰🇭", "855": "🇰🇭",
    "china": "🇨🇳", "86": "🇨🇳",
    "georgia": "🇬🇪", "995": "🇬🇪",
    "hong kong": "🇭🇰", "852": "🇭🇰",
    "india": "🇮🇳", "91": "🇮🇳",
    "indonesia": "🇮🇩", "62": "🇮🇩",
    "iran": "🇮🇷", "98": "🇮🇷",
    "iraq": "🇮🇶", "964": "🇮🇶",
    "israel": "🇮🇱", "972": "🇮🇱",
    "japan": "🇯🇵", "81": "🇯🇵",
    "jordan": "🇯🇴", "962": "🇯🇴",
    "kazakhstan": "🇰🇿", "7": "🇰🇿",
    "kuwait": "🇰🇼", "965": "🇰🇼",
    "kyrgyzstan": "🇰🇬", "996": "🇰🇬",
    "laos": "🇱🇦", "856": "🇱🇦",
    "lebanon": "🇱🇧", "961": "🇱🇧",
    "macau": "🇲🇴", "853": "🇲🇴",
    "malaysia": "🇲🇾", "60": "🇲🇾",
    "maldives": "🇲🇻", "960": "🇲🇻",
    "mongolia": "🇲🇳", "976": "🇲🇳",
    "myanmar": "🇲🇲", "95": "🇲🇲",
    "nepal": "🇳🇵", "977": "🇳🇵",
    "north korea": "🇰🇵", "850": "🇰🇵",
    "oman": "🇴🇲", "968": "🇴🇲",
    "pakistan": "🇵🇰", "92": "🇵🇰",
    "palestine": "🇵🇸", "970": "🇵🇸",
    "philippines": "🇵🇭", "63": "🇵🇭",
    "qatar": "🇶🇦", "974": "🇶🇦",
    "russia": "🇷🇺", "7": "🇷🇺",
    "saudi arabia": "🇸🇦", "966": "🇸🇦",
    "singapore": "🇸🇬", "65": "🇸🇬",
    "south korea": "🇰🇷", "82": "🇰🇷",
    "sri lanka": "🇱🇰", "94": "🇱🇰",
    "syria": "🇸🇾", "963": "🇸🇾",
    "taiwan": "🇹🇼", "886": "🇹🇼",
    "tajikistan": "🇹🇯", "992": "🇹🇯",
    "thailand": "🇹🇭", "66": "🇹🇭",
    "timor-leste": "🇹🇱", "670": "🇹🇱",
    "turkey": "🇹🇷", "90": "🇹🇷",
    "turkmenistan": "🇹🇲", "993": "🇹🇲",
    "united arab emirates": "🇦🇪", "uae": "🇦🇪", "971": "🇦🇪",
    "uzbekistan": "🇺🇿", "998": "🇺🇿",
    "vietnam": "🇻🇳", "84": "🇻🇳",
    "yemen": "🇾🇪", "967": "🇾🇪",

    # Europe
    "albania": "🇦🇱", "355": "🇦🇱",
    "andorra": "🇦🇩", "376": "🇦🇩",
    "austria": "🇦🇹", "43": "🇦🇹",
    "belarus": "🇧🇾", "375": "🇧🇾",
    "belgium": "🇧🇪", "32": "🇧🇪",
    "bosnia and herzegovina": "🇧🇦", "387": "🇧🇦",
    "bulgaria": "🇧🇬", "359": "🇧🇬",
    "croatia": "🇭🇷", "385": "🇭🇷",
    "cyprus": "🇨🇾", "357": "🇨🇾",
    "czech republic": "🇨🇿", "czechia": "🇨🇿", "420": "🇨🇿",
    "denmark": "🇩🇰", "45": "🇩🇰",
    "estonia": "🇪🇪", "372": "🇪🇪",
    "finland": "🇫🇮", "358": "🇫🇮",
    "france": "🇫🇷", "33": "🇫🇷",
    "germany": "🇩🇪", "49": "🇩🇪",
    "greece": "🇬🇷", "30": "🇬🇷",
    "hungary": "🇭🇺", "36": "🇭🇺",
    "iceland": "🇮🇸", "354": "🇮🇸",
    "ireland": "🇮🇪", "353": "🇮🇪",
    "italy": "🇮🇹", "39": "🇮🇹",
    "kosovo": "🇽🇰", "383": "🇽🇰",
    "latvia": "🇱🇻", "371": "🇱🇻",
    "liechtenstein": "🇱🇮", "423": "🇱🇮",
    "lithuania": "🇱🇹", "370": "🇱🇹",
    "luxembourg": "🇱🇺", "352": "🇱🇺",
    "malta": "🇲🇹", "356": "🇲🇹",
    "moldova": "🇲🇩", "373": "🇲🇩",
    "monaco": "🇲🇨", "377": "🇲🇨",
    "montenegro": "🇲🇪", "382": "🇲🇪",
    "netherlands": "🇳🇱", "31": "🇳🇱",
    "north macedonia": "🇲🇰", "389": "🇲🇰",
    "norway": "🇳🇴", "47": "🇳🇴",
    "poland": "🇵🇱", "48": "🇵🇱",
    "portugal": "🇵🇹", "351": "🇵🇹",
    "romania": "🇷🇴", "40": "🇷🇴",
    "san marino": "🇸🇲", "378": "🇸🇲",
    "serbia": "🇷🇸", "381": "🇷🇸",
    "slovakia": "🇸🇰", "421": "🇸🇰",
    "slovenia": "🇸🇮", "386": "🇸🇮",
    "spain": "🇪🇸", "34": "🇪🇸",
    "sweden": "🇸🇪", "46": "🇸🇪",
    "switzerland": "🇨🇭", "41": "🇨🇭",
    "ukraine": "🇺🇦", "380": "🇺🇦",
    "uk": "🇬🇧", "united kingdom": "🇬🇧", "44": "🇬🇧",
    "vatican city": "🇻🇦", "379": "🇻🇦",

    # North America
    "antigua and barbuda": "🇦🇬", "1": "🇦🇬",
    "bahamas": "🇧🇸", "1": "🇧🇸",
    "barbados": "🇧🇧", "1": "🇧🇧",
    "belize": "🇧🇿", "501": "🇧🇿",
    "canada": "🇨🇦", "1": "🇨🇦",
    "costa rica": "🇨🇷", "506": "🇨🇷",
    "cuba": "🇨🇺", "53": "🇨🇺",
    "dominica": "🇩🇲", "1": "🇩🇲",
    "dominican republic": "🇩🇴", "1": "🇩🇴",
    "el salvador": "🇸🇻", "503": "🇸🇻",
    "grenada": "🇬🇩", "1": "🇬🇩",
    "guatemala": "🇬🇹", "502": "🇬🇹",
    "haiti": "🇭🇹", "509": "🇭🇹",
    "honduras": "🇭🇳", "504": "🇭🇳",
    "jamaica": "🇯🇲", "1": "🇯🇲",
    "mexico": "🇲🇽", "52": "🇲🇽",
    "nicaragua": "🇳🇮", "505": "🇳🇮",
    "panama": "🇵🇦", "507": "🇵🇦",
    "saint kitts and nevis": "🇰🇳", "1": "🇰🇳",
    "saint lucia": "🇱🇨", "1": "🇱🇨",
    "saint vincent and the grenadines": "🇻🇨", "1": "🇻🇨",
    "trinidad and tobago": "🇹🇹", "1": "🇹🇹",
    "usa": "🇺🇸", "united states": "🇺🇸", "1": "🇺🇸",

    # South America
    "argentina": "🇦🇷", "54": "🇦🇷",
    "bolivia": "🇧🇴", "591": "🇧🇴",
    "brazil": "🇧🇷", "55": "🇧🇷",
    "chile": "🇨🇱", "56": "🇨🇱",
    "colombia": "🇨🇴", "57": "🇨🇴",
    "ecuador": "🇪🇨", "593": "🇪🇨",
    "guyana": "🇬🇾", "592": "🇬🇾",
    "paraguay": "🇵🇾", "595": "🇵🇾",
    "peru": "🇵🇪", "51": "🇵🇪",
    "suriname": "🇸🇷", "597": "🇸🇷",
    "uruguay": "🇺🇾", "598": "🇺🇾",
    "venezuela": "🇻🇪", "58": "🇻🇪",

    # Oceania
    "australia": "🇦🇺", "61": "🇦🇺",
    "fiji": "🇫🇯", "679": "🇫🇯",
    "kiribati": "🇰🇮", "686": "🇰🇮",
    "marshall islands": "🇲🇭", "692": "🇲🇭",
    "micronesia": "🇫🇲", "691": "🇫🇲",
    "nauru": "🇳🇷", "674": "🇳🇷",
    "new zealand": "🇳🇿", "64": "🇳🇿",
    "palau": "🇵🇼", "680": "🇵🇼",
    "papua new guinea": "🇵🇬", "675": "🇵🇬",
    "samoa": "🇼🇸", "685": "🇼🇸",
    "solomon islands": "🇸🇧", "677": "🇸🇧",
    "tonga": "🇹🇴", "676": "🇹🇴",
    "tuvalu": "🇹🇻", "688": "🇹🇻",
    "vanuatu": "🇻🇺", "678": "🇻🇺"
}

# Simple HTTP Server for Render / UptimeRobot health checks
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ANU Premium Bot is alive and running!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress routine HTTP access logs to keep terminal clean
        return

def run_health_server():
    server = HTTPServer(("0.0.0.0", 10000), HealthCheckHandler)
    server.serve_forever()

def get_flag_automatically(text: str) -> str:
    """Scans text for any matching country name or prefix code to automatically resolve the flag emoji."""
    lower_text = text.lower()
    for key, flag in COUNTRY_FLAG_MAP.items():
        if key in lower_text:
            return flag
    return "🌐"

def extract_otp_code(content: str) -> str:
    """Extracts just the clean OTP code (e.g. 4 to 8 digits) from raw SMS text."""
    if not content:
        return ""
    match = re.search(r'\b(\d{4,8})\b', content)
    if match:
        return match.group(1)
    return content.strip()

def mask_phone_number(num_str: str) -> str:
    """Masks a phone number for public channel privacy (e.g., +25197****1222)."""
    if not num_str or len(num_str) < 8:
        return num_str
    return num_str[:5] + "****" + num_str[-4:]

# Helper functions for Supabase database operations
def get_managed_ranges():
    """Fetches all managed ranges from Supabase."""
    try:
        response = supabase.table("bot_ranges").select("*").execute()
        return response.data or []
    except Exception as e:
        logging.error(f"Failed to fetch ranges from Supabase: {e}")
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the welcome message, saves user to Supabase, and brings up the bottom reply keyboard."""
    user = update.effective_user
    
    # Save or update user in Supabase
    try:
        supabase.table("bot_users").upsert({
            "user_id": user.id,
            "first_name": user.first_name,
            "username": user.username
        }, on_conflict="user_id").execute()
    except Exception as e:
        logging.error(f"Failed to save user to Supabase: {e}")

    welcome_text = (
        "✨ **Welcome to ANU PREMIUM OTP** ✨\n\n"
        "🚀 *Your premium hub for virtual numbers and live 2FA code automation.*\n"
        "👇 **Select an option from the custom keyboard below:**"
    )
    
    keyboard = [
        [
            KeyboardButton("📱 Get Number"),
            KeyboardButton("⚡ Active Engine")
        ],
        [
            KeyboardButton("🌐 Live Feed"),
            KeyboardButton("🎁 Referrals")
        ],
        [
            KeyboardButton("👤 My Profile"),
            KeyboardButton("🎧 Support Hub")
        ]
    ]
    
    reply_markup = ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True, 
        one_time_keyboard=False
    )
    
    if update.message:
        await update.message.reply_text(
            welcome_text, 
            parse_mode="Markdown", 
            reply_markup=reply_markup
        )

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Interactive Admin Control Panel using colorful inline buttons."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ **Access Denied:** You are not authorized to use the admin panel.")
        return

    admin_text = (
        f"🛠 **ANU Admin Control Panel** 🛠\n\n"
        f"📢 **OTP Channel Link:** `{OTP_CHANNEL_URL}`\n\n"
        f"👇 *Select an administrative action below:*"
    )
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Range", callback_data="admin_add_prompt"),
         InlineKeyboardButton("🗑 Delete Specific Range", callback_data="admin_del_range_prompt")],
        [InlineKeyboardButton("🔴 Clear All Ranges", callback_data="admin_clear"),
         InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast_prompt")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(admin_text, parse_mode="Markdown", reply_markup=reply_markup)

async def admin_inline_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles admin inline button actions."""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.answer("Unauthorized action.", show_alert=True)
        return

    data = query.data
    if data == "admin_add_prompt":
        await query.answer()
        context.user_data["waiting_for_range"] = True
        await query.message.reply_text(
            "✍️ **Send the new range in this format (Flag will be auto-matched from any country name or prefix code!):**\n\n`Service | Label | Range`\n👉 *Example:* `Telegram | Syrian 963 | 963XXX`",
            parse_mode="Markdown"
        )
    elif data == "admin_del_range_prompt":
        await query.answer()
        managed_ranges = get_managed_ranges()
        if not managed_ranges:
            await query.message.reply_text("⚠️ **No ranges available to delete.**", parse_mode="Markdown")
            return
        
        keyboard = []
        for r in managed_ranges:
            r_val = r.get('range_val', r.get('range'))
            label_text = f"{r.get('flag', '🌐')} [{r['service']}] {r['label']} ({r_val})"
            keyboard.append([InlineKeyboardButton(f"❌ Delete: {label_text}", callback_data=f"del_rng_{r['id']}")])
        
        await query.message.reply_text("🗑 **Select the specific range you want to delete:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("del_rng_"):
        await query.answer()
        rng_id = data.replace("del_rng_", "")
        try:
            supabase.table("bot_ranges").delete().eq("id", int(rng_id)).execute()
            await query.edit_message_text("✅ **Selected range successfully deleted from Supabase.**", parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ **Failed to delete range:** {e}", parse_mode="Markdown")
    elif data == "admin_broadcast_prompt":
        await query.answer()
        context.user_data["waiting_for_broadcast"] = True
        await query.message.reply_text(
            "📢 **Send the message text/content you want to broadcast to all registered bot users:**",
            parse_mode="Markdown"
        )
    elif data == "admin_clear":
        try:
            supabase.table("bot_ranges").delete().neq("id", 0).execute()
        except Exception as e:
            logging.error(f"Failed to clear ranges from Supabase: {e}")
            
        await query.answer("All ranges cleared!", show_alert=True)
        await query.edit_message_text("🗑 **All custom ranges have been cleared from Supabase.** Use `/admin` to manage them.", parse_mode="Markdown")

async def handle_reply_keyboard_clicks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captures inputs from custom bottom reply keyboard and admin text setup prompts."""
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id == ADMIN_ID and context.user_data.get("waiting_for_range"):
        if text.count("|") != 2:
            await update.message.reply_text("⚠️ **Format error!** Use: `Service | Label | Range`\nExample: `Telegram | Syrian 963 | 963XXX`", parse_mode="Markdown")
            return
        
        parts = [p.strip() for p in text.split("|")]
        service = parts[0]
        label = parts[1]
        range_val = parts[2]

        auto_flag = get_flag_automatically(label + " " + range_val)

        try:
            supabase.table("bot_ranges").insert({
                "service": service,
                "flag": auto_flag,
                "label": label,
                "range_val": range_val
            }).execute()
        except Exception as e:
            await update.message.reply_text(f"❌ **Failed to save range to Supabase:** {e}")
            return

        context.user_data["waiting_for_range"] = False
        
        await update.message.reply_text(f"✅ **Successfully saved range to Supabase with auto-matched flag!**\n📌 **Service:** `{service}`\n{auto_flag} **Label:** `{label}`\n🔢 **Range:** `{range_val}`\n\nType `/admin` to view panel.", parse_mode="Markdown")
        return

    if user_id == ADMIN_ID and context.user_data.get("waiting_for_broadcast"):
        context.user_data["waiting_for_broadcast"] = False
        broadcast_text = update.message.text
        
        try:
            users_res = supabase.table("bot_users").select("user_id").execute()
            users = users_res.data or []
        except Exception as e:
            await update.message.reply_text(f"❌ **Failed to fetch users from database for broadcast:** {e}")
            return

        status_msg = await update.message.reply_text(f"🚀 **Broadcasting message to {len(users)} users...**", parse_mode="Markdown")
        
        success_count = 0
        fail_count = 0
        for u in users:
            uid = u.get("user_id")
            if uid:
                try:
                    await context.bot.send_message(
                        chat_id=int(uid),
                        text=f"📢 **Announcement from Admin:**\n\n{broadcast_text}",
                        parse_mode="Markdown"
                    )
                    success_count += 1
                    await asyncio.sleep(0.05) # Prevent flood limits
                except Exception:
                    fail_count += 1
                    
        await status_msg.edit_text(f"✅ **Broadcast Completed!**\n\n🟢 **Successfully Sent:** {success_count}\n🔴 **Failed:** {fail_count}", parse_mode="Markdown")
        return

    if "Get Number" in text:
        managed_ranges = get_managed_ranges()
        if not managed_ranges:
            if user_id == ADMIN_ID:
                await update.message.reply_text("⚠️ **No numbers/ranges available.** Please use `/admin` to add ranges first.", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ **No numbers available for now.** Please check back later! 🚀", parse_mode="Markdown")
            return
        
        services = sorted(list(set(r["service"] for r in managed_ranges)))
        keyboard = [[InlineKeyboardButton(f"🛡️ {s}", callback_data=f"srv_{s}")] for s in services]
        await update.message.reply_text("🛠 **Select a Service:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif "Active Engine" in text:
        result = fetch_active_ranges()
        if result and "data" in result and "active_ranges" in result["data"]:
            ranges = result["data"]["active_ranges"]
            msg = "⚡ **Active Engine Routes:** ⚡\n\n"
            for r in ranges:
                msg += f"• 🌐 `{r.get('range')}` | 🛡️ {r.get('service')} - 🔥 {r.get('hits')} hits\n"
        else:
            msg = "❌ **Failed to fetch active routing ranges.**"
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif "Live Feed" in text:
        result = fetch_global_broadcast()
        if result and "data" in result:
            broadcasts = result["data"]
            msg = "🌐 **Global Live Console Feed:** 📡\n\n"
            for b in broadcasts[:5]:
                msg += f"• 📱 `{b.get('number')}` | 🛡️ {b.get('service')}\n  🔑 `{b.get('otp')}`\n\n"
        else:
            msg = "❌ **Failed to fetch global broadcast feed.**"
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif "Referrals" in text:
        bot_username = (await context.bot.get_me()).username
        await update.message.reply_text(f"🎁 **Your Referral Link:** 🎯\n🔗 `https://t.me/{bot_username}?start={user_id}`", parse_mode="Markdown")

    elif "My Profile" in text:
        user = update.effective_user
        await update.message.reply_text(f"👤 **ANU User Profile** 🔵\n\n🆔 **User ID:** `{user.id}`\n👤 **Name:** {user.first_name}\n🟢 **Status:** Active & Verified", parse_mode="Markdown")

    elif "Support Hub" in text:
        keyboard = [[InlineKeyboardButton("💬 Contact Support Agent", url="https://t.me/anstans")]]
        await update.message.reply_text("🧑‍💻 **ANU Support Hub:** Click below to message support directly:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def fetch_code_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inline handler triggered when clicking 'Fetch Code' under the provisioned numbers view."""
    query = update.callback_query
    await query.answer("Fetching latest SMS / OTP payloads...", show_alert=False)
    
    result = fetch_sms_payloads()
    if result and "data" in result and "otps" in result["data"]:
        otps = result["data"]["otps"]
        if not otps:
            msg = "📭 **No live SMS records found right now.**"
        else:
            msg = "📬 **Live 2FA / SMS Payloads:** 🔑\n\n"
            for item in otps[:5]:
                msg += f"• 📱 **Num:** `{item.get('number')}`\n  🔑 `{item.get('otp')}`\n  🕒 *{item.get('created_at')}*\n\n"
    else:
        msg = "❌ **Failed to fetch live SMS payloads.**"
    
    await query.message.reply_text(msg, parse_mode="Markdown")

async def provision_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles service selection, auto-matched country/range selection, and number provisioning."""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    data = query.data
    if data == "close_msg":
        await query.message.delete()
        return

    managed_ranges = get_managed_ranges()

    if data.startswith("srv_"):
        selected_service = data.replace("srv_", "")
        matching_ranges = [r for r in managed_ranges if r["service"] == selected_service]
        
        keyboard = []
        for r in matching_ranges:
            flag_icon = r.get("flag", "🌐")
            r_val = r.get("range_val", r.get("range"))
            keyboard.append([InlineKeyboardButton(f"{flag_icon} 🔹 {r['label']}", callback_data=f"prov_{r_val}")])
        
        keyboard.append([InlineKeyboardButton("« Back to Services", callback_data="menu_get_number")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"🛡️ **Selected Service:** 🟣 `{selected_service}`\n\n👇 **Select Country / Range Pattern:**", parse_mode="Markdown", reply_markup=reply_markup)
        return
        
    if data.startswith("prov_"):
        selected_range = data.replace("prov_", "")
        
        matched_item = next((r for r in managed_ranges if r.get("range_val", r.get("range")) == selected_range), {})
        flag_icon = matched_item.get("flag", "🌐")
        
        # If user clicked "Change Numbers", delete the previous dashboard message completely and send fresh at bottom
        is_change_action = query.message and query.message.text and "ANU Numbers Secured & Bound" in query.message.text
        if is_change_action:
            try:
                await query.message.delete()
            except Exception:
                pass
            status_msg = await context.bot.send_message(
                chat_id=user_id,
                text=f"⏳ **Provisioning 3 new virtual numbers using range** `{selected_range}`...",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(f"⏳ **Provisioning 3 virtual numbers using range** `{selected_range}`...", parse_mode="Markdown")
            status_msg = query.message
        
        provisioned_numbers = []
        for _ in range(3):
            result = provision_virtual_number(range_prefix=selected_range)
            if result and "data" in result:
                num_data = result["data"]
                num = num_data.get("number") or num_data.get("full_number") or num_data.get("copy")
                if num:
                    provisioned_numbers.append(num)
        
        if provisioned_numbers:
            USER_ACTIVE_NUMBERS[str(user_id)] = provisioned_numbers
            
            # Clean dashboard message without extra instruction text
            msg = "✅ **ANU Numbers Secured & Bound!** 🟢"
            
            keyboard = []
            for num in provisioned_numbers:
                keyboard.append([InlineKeyboardButton(f"{flag_icon} 📋 {num}", copy_text=CopyTextButton(text=num))])
            
            keyboard.append([InlineKeyboardButton("🔐 🟡 Fetch Code", callback_data="inline_fetch_code")])
            
            keyboard.append([
                InlineKeyboardButton("🔄 🔵 Change Numbers", callback_data=f"prov_{selected_range}"),
                InlineKeyboardButton("📢 🟣 OTP Channel ↗", url=OTP_CHANNEL_URL)
            ])
            keyboard.append([InlineKeyboardButton("❌ 🔴 Close Dashboard", callback_data="close_msg")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if is_change_action:
                await status_msg.edit_text(text=msg, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                await query.edit_message_text(text=msg, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            error_msg = "❌ **Failed to provision virtual numbers.** Please check API limits or try another range."
            if is_change_action:
                await status_msg.edit_text(text=error_msg, parse_mode="Markdown")
            else:
                await query.edit_message_text(text=error_msg, parse_mode="Markdown")

async def background_otp_poller(application):
    """Background task polling Zenex API, broadcasting full message with masked number to channel and clean format to user DM."""
    await application.bot.initialize()
    while True:
        try:
            if USER_ACTIVE_NUMBERS:
                response = fetch_sms_payloads()
                if response and "data" in response and "otps" in response["data"]:
                    otps = response["data"]["otps"]
                    for record in otps:
                        nid = record.get("nid")
                        number = record.get("number")
                        raw_otp_content = record.get("otp")
                        country = record.get("country", "Ethiopia")
                        operator = record.get("operator", "N/A")
                        created_at = record.get("created_at", "N/A")

                        clean_code = extract_otp_code(raw_otp_content)

                        if nid and nid not in PROCESSED_NIDS:
                            clean_sms_number = str(number).replace("+", "").strip()

                            for uid, num_list in USER_ACTIVE_NUMBERS.items():
                                clean_user_numbers = [str(n).replace("+", "").strip() for n in num_list]

                                if clean_sms_number in clean_user_numbers:
                                    PROCESSED_NIDS.add(nid)
                                    if len(PROCESSED_NIDS) > 2000:
                                        PROCESSED_NIDS.pop()
                                    
                                    # Mask the phone number for the public channel
                                    masked_number = mask_phone_number(str(number))

                                    # Full message broadcast to the public channel with masked number
                                    channel_msg = (
                                        f"🔔 **[ANU Premium] New OTP Received!** 🟢\n\n"
                                        f"📱 **Number:** `{masked_number}`\n"
                                        f"🌍 **Country:** {country} ({operator})\n"
                                        f"💬 **Content:**\n`{raw_otp_content}`\n\n"
                                        f"🕒 *{created_at}*"
                                    )
                                    try:
                                        await application.bot.send_message(
                                            chat_id=int(OTP_GROUP_CHAT_ID),
                                            text=channel_msg,
                                            parse_mode="Markdown"
                                        )
                                    except Exception as e:
                                        logging.error(f"Failed to post OTP to channel: {e}")

                                    # Active user DM notification with clean text and isolated copy code button
                                    user_dm_msg = (
                                        f"🔔 **ANU New OTP Code Received!** 🟡\n\n"
                                        f"📱 **Number:** `{number}`\n"
                                        f"🌍 **Country:** {country}"
                                    )
                                    user_keyboard = InlineKeyboardMarkup([
                                        [InlineKeyboardButton(f"🔑 📋 {clean_code}", copy_text=CopyTextButton(text=clean_code))]
                                    ])
                                    try:
                                        await application.bot.send_message(
                                            chat_id=int(uid),
                                            text=user_dm_msg,
                                            parse_mode="Markdown",
                                            reply_markup=user_keyboard
                                        )
                                    except Exception as e:
                                        logging.error(f"Failed to deliver OTP to user {uid}: {e}")
        except Exception as e:
            logging.error(f"Error in background OTP poller: {e}")
        
        await asyncio.sleep(4)

async def post_init(application):
    """Starts the background API polling task when the bot starts up."""
    application.create_task(background_otp_poller(application))

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN is not set in your .env file.")
        return

    # Start the lightweight HTTP health check server in a background thread for Render & UptimeRobot
    threading.Thread(target=run_health_server, daemon=True).start()
    logging.info("🌐 Health check web server started on port 10000.")

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", cmd_admin))
    application.add_handler(CallbackQueryHandler(admin_inline_handler, pattern="^admin_"))
    application.add_handler(CallbackQueryHandler(admin_inline_handler, pattern="^del_rng_"))
    application.add_handler(CallbackQueryHandler(fetch_code_callback_handler, pattern="^inline_fetch_code$"))
    application.add_handler(CallbackQueryHandler(provision_callback_handler, pattern="^(srv_|prov_|close_)"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_reply_keyboard_clicks))

    print("🤖 ANU PREMIUM OTP Bot is running cleanly with Supabase storage and Uptime integration enabled!")
    application.run_polling()

if __name__ == "__main__":
    main()
