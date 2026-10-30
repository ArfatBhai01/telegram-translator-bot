import os
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from lingua import Language, LanguageDetectorBuilder
from languages import LANGUAGES, resolve_lang, get_name
from groq import Groq

# 1. Setup
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_KEY:
    print("❌ ERROR: GROQ_API_KEY is missing in Render Environment Variables!")
    groq_client = None
else:
    groq_client = Groq(api_key=GROQ_KEY)
    print("✅ Groq AI loaded successfully!")

# Initialize the smart language detector (Low Memory Mode)
detector = LanguageDetectorBuilder.from_all_languages().with_low_accuracy_mode().build()

# 2. Translation Engine
def detect_lang(text: str) -> str:
    try:
        lang = detector.detect_language_of(text)
        if not lang: return "en"
        code = lang.iso_code_639_1.name.lower()
        if code in ("zh-cn", "zh"): return "zh-CN"
        if code == "zh-tw": return "zh-TW"
        return code if code in LANGUAGES else "en"
    except Exception:
        return "en"

def translate_text(text: str, target_code: str, source_code: str = "auto") -> str:
    if source_code == target_code:
        return text
    
    if not groq_client:
        return "⚠️ Error: AI is not configured. Please contact @Lustcoded."

    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": f"Translate this text to {get_name(target_code)}. Reply ONLY with the translation, no explanations:\n{text}"}],
            temperature=0.2
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"AI failed: {e}")
        return f"⚠️ AI Error: {str(e)[:50]}"

# 3. Handlers
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🔥 *AI Translation Bot*\n\n"
        "I automatically translate every message in this chat.\n\n"
        "Use `/set <language>` to change the language (e.g., `/set korean`).\n\n"
        "💡 *Need help?*\n"
        "Contact the developer: **@Lustcoded**"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ *Help Menu*\n\n"
        "• `/start` - Welcome message\n"
        "• `/set <lang>` - Change target language\n"
        "• `/langs` - See all 130+ languages\n\n"
        "💡 *Need help?*\n"
        "Contact the developer: **@Lustcoded**"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def set_lang_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        return await update.message.reply_text("Usage: `/set <language>`\ne.g. `/set korean`", parse_mode="Markdown")
    
    target = resolve_lang(" ".join(ctx.args))
    if not target:
        return await update.message.reply_text("❌ Unknown language. Use /langs to see the list.")
        
    settings = get_settings(update.effective_chat.id)
    settings["my_lang"] = target
    await update.message.reply_text(f"✅ Done! I will now automatically translate all messages to *{get_name(target)}*.", parse_mode="Markdown")

async def langs_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    items = sorted(LANGUAGES.items(), key=lambda x: x[1][0])
    lines = [f"`{code}` — {name}" for code, (name, _) in items]
    chunk, out = [], []
    for line in lines:
        chunk.append(line)
        if len("\n".join(chunk)) > 3500:
            out.append("\n".join(chunk)); chunk = []
    if chunk: out.append("\n".join(chunk))
    for part in out:
        await update.message.reply_text(part, parse_mode="Markdown")

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text = update.message.text
    if text.startswith("/"): return

    chat_id = update.effective_chat.id
    settings = get_settings(chat_id)
    
    src_lang = detect_lang(text)
    target_lang = settings["my_lang"]

    if src_lang == target_lang: return

    await ctx.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    translated = translate_text(text, target_lang, src_lang)
    reply_text = f"🌐 *Translation* ({get_name(src_lang)} → {get_name(target_lang)})\n\n{translated}"

    await update.message.reply_text(
        reply_text, 
        parse_mode="Markdown", 
        reply_to_message_id=update.message.message_id
    )

# 4. Menu Settings
user_settings = {}
DEFAULT_SETTINGS = {"my_lang": "en"}

def get_settings(chat_id):
    if chat_id not in user_settings:
        user_settings[chat_id] = DEFAULT_SETTINGS.copy()
    return user_settings[chat_id]

# 5. Run Bot & Web Server
async def post_init(application: Application) -> None:
    commands = [
        BotCommand("start", "Show welcome message"),
        BotCommand("set", "Change target language"),
        BotCommand("langs", "See all 130+ languages"),
        BotCommand("help", "Get help & contact info")
    ]
    await application.bot.set_my_commands(commands)

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    httpd = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    httpd.serve_forever()

def main():
    if not BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN is missing!")
        return
    
    threading.Thread(target=run_web_server, daemon=True).start()
    
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("set", set_lang_text))
    app.add_handler(CommandHandler("langs", langs_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 Bot is running on 100% AI Engine!")
        # This tells the library to not crash the whole app on a timeout
    # and to try again after a short delay.
    app.run_polling(
        close_loop=False,
        bootstrap_retries=5,
        read_timeout=60
    )

if __name__ == "__main__":
    main()
