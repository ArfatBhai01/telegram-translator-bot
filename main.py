import os
import threading
from flask import Flask
from bot import main as run_bot_main

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running perfectly!"

def run_flask():
    # Run Flask in the background on Render's port
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # 1. Start Flask in a background thread (keeps Render happy)
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # 2. Run the Telegram bot in the MAIN thread (fixes the crash)
    print("🚀 Starting Telegram Bot in main thread...")
    run_bot_main()
