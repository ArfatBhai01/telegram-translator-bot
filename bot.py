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

# 2. Translation Engine (Triple Fallback)
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

def translate_google(text, src, tgt):
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": src, "tl": tgt, "dt": "t", "q": text}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(url, params=params, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            return "".join([item[0] for item in data[0] if item[0]])
    except:
        pass
    return None

def translate_microsoft(text, tgt):
    try:
        t_code = tgt.lower()
        if t_code == "zh-cn": t_code = "zh-Hans"
        if t_code == "zh-tw": t_code = "zh-Hant"
        url = f"https://api-edge.cognitive.microsofttranslator.com/translate?api-version=3.0&to={t_code}"
        headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
        r = requests.post(url, headers=headers, json=[{"Text": text}], timeout=5)
        if r.status_code == 200:
            return r.json()[0]["translations"][0]["text"]
    except:
        pass
    return None

def translate_mymemory(text, src, tgt):
    try:
        url = f"https://api.mymemory.translated.net/get?q={requests.utils.quote(text)}&langpair={src}|{tgt}"
        r = requests.get(url, timeout=5).json()
        if "responseData" in r and r["responseData"]["translatedText"]:
            # Ignore MyMemory's daily limit warning
            if "MYMEMORY WARNING" not in r["responseData"]["translatedText"]:
                return r["responseData"]["translatedText"]
    except:
        pass
    return None

def translate_text(text: str, target_code: str, source_code: str = "auto") -> str:
    if source_code == target_code:
        return text
        
    # Try 1: Google
    result = translate_google(text, source_code, target_code)
    if result: return result

    # Try 2: Microsoft
    result = translate_microsoft(text, target_code)
    if result: return result

    # Try 3: MyMemory
    result = translate_mymemory(text, source_code, target_code)
    if result: return result

    return "⚠️ All engines blocked. Try again later."

# 3. Handlers
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 *AI Translation Bot*\n\nI translate everything.\n\nUse `/set <language>` to change the language.\n\n💡 *Need help?* Contact: **@Lustcoded**", parse_mode="Markdown")

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
    print("🚀 Bot is running on Triple Fallback Engine!")
    app.run_polling(close_loop=False, bootstrap_retries=5, read_timeout=60)

if __name__ == "__main__":
    main()
