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
from deep_translator import GoogleTranslator
from langdetect import detect, DetectorFactory
from languages import LANGUAGES, resolve_lang, get_name
import translators as ts

# 1. Setup
load_dotenv()
DetectorFactory.seed = 0
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")

groq_client = None
if GROQ_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_KEY)
    except Exception:
        pass

# 2. Translation Engine
def detect_lang(text: str) -> str:
    try:
        code = detect(text)
        if code in ("zh-cn", "zh"): return "zh-CN"
        if code == "zh-tw": return "zh-TW"
        return code if code in LANGUAGES else "en"
    except Exception:
        return "en"

def translate_text(text: str, target_code: str, source_code: str = "auto") -> str:
    if source_code == target_code:
        return text
    
    try:
        result = GoogleTranslator(source=source_code, target=target_code).translate(text)
        if result: return result
    except Exception:
        pass
        
    try:
        t_code = target_code.lower()
        if t_code == "zh-cn": t_code = "zh-Hans"
        if t_code == "zh-tw": t_code = "zh-Hant"
        result = ts.translate_text(text, translator='bing', from_language='auto', to_language=t_code)
        if result: return result
    except Exception:
        pass

    if groq_client:
        try:
            resp = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": f"Translate this to {get_name(target_code)}. Reply ONLY with the translation:\n{text}"}],
                temperature=0.2
            )
            return f"🤖 {resp.choices[0].message.content.strip()}"
        except Exception:
            pass

    return "⚠️ Translation failed. Please try again in a few seconds."

# 3. Handlers
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🔥 *AI Translation Bot*\n\n"
        "I automatically translate every message in this chat into **English**.\n\n"
        "Need another language? Use `/set <language>` (e.g., `/set korean`).\n\n"
        "💡 *Need help or have questions?*\n"
        "Contact the developer: **@Lustcoded**"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "ℹ️ *Help Menu*\n\n"
        "• `/start` - Welcome message\n"
        "• `/set <lang>` - Change target language (e.g., `/set spanish`)\n"
        "• `/langs` - See all 130+ supported languages\n\n"
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
        print("❌ ERROR: BOT_TOKEN is missing in .env file!")
        return
    
    # Start the web server in a background thread
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # Start the bot
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("set", set_lang_text))
    app.add_handler(CommandHandler("langs", langs_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 Bot is running safely with Polling and Free Web Server!")
    app.run_polling()

if __name__ == "__main__":
    main()