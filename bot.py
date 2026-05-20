"""
Telegram Channel Manager Bot
Features:
  - Messages/Posts Schedule karna
  - Auto-reply karna
  - New members ko welcome karna
  - Channel stats track karna
  - Auto join request accept karna
"""

import logging
import asyncio
from datetime import datetime, time
from typing import Optional
import json
import os

from telegram import (
    Update,
    ChatMemberUpdated,
    ChatJoinRequest,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    ChatJoinRequestHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    JobQueue,
)
from telegram.constants import ParseMode
import pytz

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")          # BotFather se milega
CHANNEL_ID = "@happymoney07"      # ya -100xxxxxxxxxx numeric ID
ADMIN_IDS = [1459165268]                    # Apna Telegram user ID daalo
TIMEZONE = "Asia/Kolkata"                  # Apna timezone

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── STATS STORAGE (JSON file) ────────────────────────────────────────────────
STATS_FILE = "stats.json"

def load_stats() -> dict:
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    return {"total_members": 0, "join_requests_accepted": 0, "messages_sent": 0, "auto_replies": 0}

def save_stats(stats: dict):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

# ─── AUTO-REPLY RULES ─────────────────────────────────────────────────────────
# keyword: reply text
AUTO_REPLIES = {
    "price": "💰 Hamare pricing ke liye yahan dekhen: [link]",
    "contact": "📞 Humse sampark karein: @admin_username",
    "join": "🎉 Channel join karne ke liye yahan click karein: [link]",
    "help": "🆘 Kisi bhi madad ke liye @admin_username se baat karein.",
    "hello": "👋 Namaste! Channel mein aapka swagat hai!",
    "hi": "👋 Hi! Kaise help kar sakta hoon aapki?",
}

# ─── WELCOME MESSAGE ──────────────────────────────────────────────────────────
WELCOME_TEXT = """
🎊 *Namaskar, {name}!*

Hamara channel join karne ke liye aapka teh dil se shukriya! 🙏

📌 *Channel ke Rules:*
• Respect karen sabko
• Spam bilkul nahi
• Topic se related posts karein

🔔 Notifications on rakhein taaki koi post miss na ho!

Koi sawaal ho toh @admin_username se poochein 😊
"""

# ─── SCHEDULED POSTS ──────────────────────────────────────────────────────────
SCHEDULED_POSTS = [
    {
        "time": "09:00",
        "message": "🌅 *Suprabhat!*\n\nAaj ka din acha ho aapka! ☀️\n\n#GoodMorning #Channel",
    },
    {
        "time": "21:00",
        "message": "🌙 *Shubh Ratri!*\n\nKal phir milenge naye updates ke saath! 😴\n\n#GoodNight",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN CHECK
# ══════════════════════════════════════════════════════════════════════════════

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ══════════════════════════════════════════════════════════════════════════════
#  /start COMMAND
# ══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📊 Stats Dekhen", callback_data="stats")],
        [InlineKeyboardButton("📅 Post Schedule Karein", callback_data="schedule_help")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        f"👋 *Namaste, {user.first_name}!*\n\n"
        "Main aapka *Channel Manager Bot* hoon 🤖\n\n"
        "Main yeh sab kar sakta hoon:\n"
        "✅ Posts schedule karna\n"
        "✅ Auto-reply\n"
        "✅ Naye members ko welcome karna\n"
        "✅ Channel stats track karna\n"
        "✅ Join requests auto-accept karna\n\n"
        "Neeche se option chunen:"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


# ══════════════════════════════════════════════════════════════════════════════
#  /stats COMMAND
# ══════════════════════════════════════════════════════════════════════════════

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Yeh command sirf admins ke liye hai!")
        return

    stats = load_stats()

    # Live member count channel se
    try:
        chat = await context.bot.get_chat(CHANNEL_ID)
        member_count = await context.bot.get_chat_member_count(CHANNEL_ID)
    except Exception:
        member_count = stats.get("total_members", "N/A")

    text = (
        "📊 *Channel Statistics*\n\n"
        f"👥 Total Members: `{member_count}`\n"
        f"✅ Join Requests Accepted: `{stats['join_requests_accepted']}`\n"
        f"📨 Messages Sent by Bot: `{stats['messages_sent']}`\n"
        f"🤖 Auto Replies: `{stats['auto_replies']}`\n\n"
        f"🕐 Last Updated: `{datetime.now().strftime('%d-%m-%Y %H:%M')}`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ══════════════════════════════════════════════════════════════════════════════
#  /post COMMAND  →  Channel mein post karo
# ══════════════════════════════════════════════════════════════════════════════

async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Yeh command sirf admins ke liye hai!")
        return

    if not context.args:
        await update.message.reply_text(
            "📝 *Usage:* `/post Aapka message yahan likhen`\n\n"
            "Example: `/post Aaj ka update: Naya feature launch ho gaya! 🎉`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    message_text = " ".join(context.args)
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=message_text,
            parse_mode=ParseMode.MARKDOWN,
        )
        stats = load_stats()
        stats["messages_sent"] += 1
        save_stats(stats)
        await update.message.reply_text("✅ Post successfully channel mein bhej di!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  /schedule COMMAND  →  Future mein post schedule karo
# ══════════════════════════════════════════════════════════════════════════════

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Yeh command sirf admins ke liye hai!")
        return

    # Usage: /schedule HH:MM Message text
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "📅 *Usage:* `/schedule HH:MM Aapka message`\n\n"
            "Example: `/schedule 18:30 Aaj shaam 6:30 baje ka update! 🎉`\n\n"
            "⏰ Time format: 24-hour (HH:MM)",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    time_str = context.args[0]
    message_text = " ".join(context.args[1:])

    try:
        hour, minute = map(int, time_str.split(":"))
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        schedule_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if schedule_time <= now:
            schedule_time = schedule_time.replace(day=now.day + 1)

        delay = (schedule_time - now).total_seconds()

        context.job_queue.run_once(
            send_scheduled_post,
            when=delay,
            data={"message": message_text, "channel_id": CHANNEL_ID},
            name=f"scheduled_{update.effective_user.id}_{time_str}",
        )

        await update.message.reply_text(
            f"✅ *Post Schedule Ho Gayi!*\n\n"
            f"⏰ Time: `{time_str}`\n"
            f"📝 Message: {message_text[:50]}{'...' if len(message_text) > 50 else ''}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except ValueError:
        await update.message.reply_text("❌ Galat time format! HH:MM use karein (e.g., 18:30)")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def send_scheduled_post(context: ContextTypes.DEFAULT_TYPE):
    """Job function: scheduled time par channel mein post karta hai."""
    data = context.job.data
    try:
        await context.bot.send_message(
            chat_id=data["channel_id"],
            text=data["message"],
            parse_mode=ParseMode.MARKDOWN,
        )
        stats = load_stats()
        stats["messages_sent"] += 1
        save_stats(stats)
        logger.info(f"Scheduled post sent: {data['message'][:30]}...")
    except Exception as e:
        logger.error(f"Scheduled post error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  DAILY SCHEDULED POSTS  (bot.py mein defined SCHEDULED_POSTS)
# ══════════════════════════════════════════════════════════════════════════════

async def send_daily_post(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=data["message"],
            parse_mode=ParseMode.MARKDOWN,
        )
        stats = load_stats()
        stats["messages_sent"] += 1
        save_stats(stats)
    except Exception as e:
        logger.error(f"Daily post error: {e}")


def setup_daily_posts(job_queue: JobQueue):
    """Daily scheduled posts setup karta hai."""
    tz = pytz.timezone(TIMEZONE)
    for post in SCHEDULED_POSTS:
        hour, minute = map(int, post["time"].split(":"))
        job_queue.run_daily(
            send_daily_post,
            time=time(hour=hour, minute=minute, tzinfo=tz),
            data={"message": post["message"]},
            name=f"daily_{post['time']}",
        )
        logger.info(f"Daily post scheduled at {post['time']} {TIMEZONE}")


# ══════════════════════════════════════════════════════════════════════════════
#  AUTO JOIN REQUEST ACCEPT
# ══════════════════════════════════════════════════════════════════════════════

async def auto_accept_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Naye join requests ko automatically accept karta hai."""
    join_request: ChatJoinRequest = update.chat_join_request
    user = join_request.from_user

    try:
        await join_request.approve()
        logger.info(f"Join request accepted: {user.full_name} ({user.id})")

        # Stats update
        stats = load_stats()
        stats["join_requests_accepted"] += 1
        save_stats(stats)

        # User ko DM mein welcome bhejo (optional)
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=WELCOME_TEXT.format(name=user.first_name),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            # Agar user ne DM block kiya ho toh skip karo
            pass

    except Exception as e:
        logger.error(f"Join request accept error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  NEW MEMBER WELCOME (Group mein aane par)
# ══════════════════════════════════════════════════════════════════════════════

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Naye members ko group/channel mein welcome karta hai."""
    result: ChatMemberUpdated = update.chat_member

    # Sirf tab jab member join kare (not left/banned)
    if result.new_chat_member.status not in ("member", "administrator"):
        return
    if result.old_chat_member.status in ("member", "administrator"):
        return

    user = result.new_chat_member.user
    chat = result.chat

    welcome_msg = WELCOME_TEXT.format(name=user.first_name)

    try:
        keyboard = [[InlineKeyboardButton("✅ Rules Padhe", callback_data="rules")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=chat.id,
            text=welcome_msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
        )

        stats = load_stats()
        stats["total_members"] = stats.get("total_members", 0) + 1
        save_stats(stats)

    except Exception as e:
        logger.error(f"Welcome message error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  AUTO-REPLY (Group messages mein keywords detect karo)
# ══════════════════════════════════════════════════════════════════════════════

async def auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Message mein keywords dhundhta hai aur auto-reply karta hai."""
    message = update.message
    if not message or not message.text:
        return

    text_lower = message.text.lower()

    for keyword, reply_text in AUTO_REPLIES.items():
        if keyword in text_lower:
            await message.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN)
            stats = load_stats()
            stats["auto_replies"] += 1
            save_stats(stats)
            logger.info(f"Auto-reply sent for keyword: {keyword}")
            break  # Ek hi reply bhejo


# ══════════════════════════════════════════════════════════════════════════════
#  CALLBACK QUERY HANDLERS (Inline button presses)
# ══════════════════════════════════════════════════════════════════════════════

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "stats":
        stats = load_stats()
        try:
            member_count = await context.bot.get_chat_member_count(CHANNEL_ID)
        except Exception:
            member_count = stats.get("total_members", "N/A")

        text = (
            "📊 *Channel Statistics*\n\n"
            f"👥 Total Members: `{member_count}`\n"
            f"✅ Join Requests Accepted: `{stats['join_requests_accepted']}`\n"
            f"📨 Messages Sent: `{stats['messages_sent']}`\n"
            f"🤖 Auto Replies: `{stats['auto_replies']}`"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

    elif query.data == "help":
        text = (
            "🆘 *Bot Commands:*\n\n"
            "👤 *Admin Commands:*\n"
            "`/post [message]` - Channel mein post bhejo\n"
            "`/schedule HH:MM [message]` - Post schedule karo\n"
            "`/stats` - Channel statistics dekho\n"
            "`/broadcast [message]` - Sabko message bhejo\n\n"
            "🌐 *Public Commands:*\n"
            "`/start` - Bot shuru karo\n"
            "`/help` - Help dekho"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

    elif query.data == "schedule_help":
        text = (
            "📅 *Post Schedule Kaise Karein:*\n\n"
            "Command: `/schedule HH:MM Message`\n\n"
            "Example:\n"
            "`/schedule 18:30 Aaj ka update! 🎉`\n\n"
            "⏰ 24-hour format use karein\n"
            "🕐 Timezone: " + TIMEZONE
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

    elif query.data == "rules":
        text = (
            "📌 *Channel Rules:*\n\n"
            "1️⃣ Sabka respect karein\n"
            "2️⃣ Spam bilkul nahi\n"
            "3️⃣ Topic se related baat karein\n"
            "4️⃣ Personal attacks nahi\n"
            "5️⃣ Admin ka decision final hai\n\n"
            "Rules toddne par ban ho sakta hai! ⚠️"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)


# ══════════════════════════════════════════════════════════════════════════════
#  /broadcast COMMAND
# ══════════════════════════════════════════════════════════════════════════════

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Yeh command sirf admins ke liye hai!")
        return

    if not context.args:
        await update.message.reply_text(
            "📢 *Usage:* `/broadcast Aapka message`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    message_text = " ".join(context.args)
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=f"📢 *BROADCAST*\n\n{message_text}",
            parse_mode=ParseMode.MARKDOWN,
        )
        await update.message.reply_text("✅ Broadcast successfully bhej di gayi!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  /help COMMAND
# ══════════════════════════════════════════════════════════════════════════════

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *Channel Manager Bot - Help*\n\n"
        "👤 *Admin Commands:*\n"
        "`/post [message]` - Channel mein post bhejo\n"
        "`/schedule HH:MM [msg]` - Post schedule karo\n"
        "`/stats` - Channel stats dekho\n"
        "`/broadcast [message]` - Channel broadcast\n\n"
        "🌐 *Public Commands:*\n"
        "`/start` - Bot shuru karo\n"
        "`/help` - Yeh message\n\n"
        "⚙️ *Auto Features (hamesha on):*\n"
        "✅ Join requests auto-accept\n"
        "✅ Naye members ko welcome\n"
        "✅ Keyword auto-reply\n"
        "✅ Daily scheduled posts"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("post", post_command))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))

    # Inline buttons
    app.add_handler(CallbackQueryHandler(button_callback))

    # Auto join request accept
    app.add_handler(ChatJoinRequestHandler(auto_accept_join_request))

    # New member welcome (groups mein)
    app.add_handler(ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER))

    # Auto-reply (messages par)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_reply))

    # Daily scheduled posts setup
    setup_daily_posts(app.job_queue)

    logger.info("Bot start ho raha hai... 🚀")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
