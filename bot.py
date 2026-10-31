import os
import logging
import threading
import requests
import uuid
import json
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

# 2. Translation Engine (Microsoft Edge Direct API - 100% Free & Unlimited)
def translate_text(text: str, target_code: str, source_code: str = "auto") -> str:
    if source_code == target_code:
        return text
        
    try:
        # Microsoft uses slightly different codes for some languages
        t_code = target_code.lower()
        if t_code == "zh-cn": t_code = "zh-Hans"
        if t_code == "zh-tw": t_code = "zh-Hant"
        if t_code == "auto": t_code = "auto-detect"
        
        url = "https://api-edge.cognitive.microsofttranslator.com/translate?api-version=3.0&to=" + t_code
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.51",
            "Content-Type": "application/json",
            "Accept": "*/*"
        }
        
        body = [{"Text": text}]
        
        response = requests.post(url, headers=headers, json=body, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data[0]["translations"][0]["text"]
        else:
            # Fallback to MyMemory if Microsoft blocks the IP
            url2 = f"https://api.mymemory.translated.net/get?q={requests.utils.quote(text)}&langpair={source_code}|{target_code}"
            res2 = requests.get(url2, timeout=10).json()
            return res2["responseData"]["translatedText"]
            
    except Exception as e:
        logging.error(f"Translation error: {e}")
        return "⚠️ Translation failed. Please try again."

# 3. Handlers
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 *AI Translation Bot*\n\nI translate everything automatically!\n\nUse `/set <language>` to change the target language.\n\n💡 *Need help?* Contact: **@Lustcoded**", parse_mode="Markdown")

async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ *Help*\n\n• `/set <lang>` - Change language\n• `/langs` - See all languages\n\n💡 *Need help?* Contact: **@Lustcoded**", parse_mode="Markdown")

async def set_lang_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args: return await update.message.reply_text("Usage: `/set <language>`")
    target = resolve_lang(" ".join(ctx.args))
    if not target: return await update.message.reply_text("❌ Unknown language. Use /langs to see the list.")
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
    target_lang = settings["my_lang"]
    
    # We let Microsoft detect the language automatically
    await ctx.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    translated = translate_text(text, target_lang, "auto")
    
    # Simple header for the reply
    reply_text = f"🌐 *Translation* (→ {get_name(target_lang)})\n\n{translated}"
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
    print("🚀 Bot is running on Microsoft Edge Unlimited Engine!")
    app.run_polling(close_loop=False, bootstrap_retries=5, read_timeout=60)

if __name__ == "__main__":
    main()
