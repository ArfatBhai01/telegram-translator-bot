import os
import logging
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from langdetect import detect, DetectorFactory
from languages import LANGUAGES, resolve_lang, get_name

# 1. Setup
load_dotenv()
DetectorFactory.seed = 0
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN")

# 2. Translation Engine (Direct Google Translate Endpoint)
def detect_lang(text: str) -> str:
    try:
        if len(text.split()) < 4:
            return "en"
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
        # Build the Google Translate URL
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": source_code,
            "tl": target_code,
            "dt": "t",
            "q": text
        }
        
        # These headers make Google think it's a real browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Referer": "https://translate.google.com/"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # The translated text is buried in the nested JSON
            translated = "".join([item[0] for item in data[0] if item[0]])
            return translated
        else:
            logging.error(f"Google status code: {response.status_code}")
            return "⚠️ Translation failed. Please try again."
            
    except Exception as e:
        logging.error(f"Translation error: {e}")
        return "⚠️ Translation failed. Please try again."

# 3. Handlers
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 *AI Translation Bot*\n\nI translate everything automatically!\n\nUse `/set <language>` to change the target language.\n\n💡 *Need help?* Contact: **@Lustcoded**", parse_mode="Markdown")

async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ *Help*\n\n• `/set <lang>` - Change language\n• `/langs` - See all languages", parse_mode="Markdown")

async def set_lang_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args: return await update.message.reply_text("Usage: `/set <language>`")
    target = resolve_lang(" ".join(ctx.args))
    if not target: return await update.message.reply_text("❌ Unknown language.")
    get_settings(update.effective_chat.id)["my_lang"] = target
    await update.message.reply_text(f"✅ Done! Translating to *{get_name(target)}*.", parse_mode="Markdown")

async def langs_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    items = sorted(LANGUAGES.items(), key=lambda x: x[1][0])
    lines = [f"`{code}` — {name}" for code, (name, _) in items]
    await update.message.reply_text("\n".join(lines)[:4000], parse_mode="Markdown")

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
    await update.message.reply_text(reply_text, parse_mode="Markdown", reply_to_message_id=update.message.message_id)

# 4. Utils
user_settings = {}
def get_settings(chat_id):
    if chat_id not in user_settings:
        user_settings[chat_id] = {"my_lang": "en"}
    return user_settings[chat_id]

async def post_init(application: Application) -> None:
    commands = [
        BotCommand("start", "Start bot"),
        BotCommand("set", "Change language"),
        BotCommand("langs", "See all languages"),
        BotCommand("help", "Help")
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
    if not BOT_TOKEN: return
    threading.Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("set", set_lang_text))
    app.add_handler(CommandHandler("langs", langs_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Bot is running on Direct Google Translate Engine!")
    app.run_polling(close_loop=False, bootstrap_retries=5, read_timeout=60)

if __name__ == "__main__":
    main()
