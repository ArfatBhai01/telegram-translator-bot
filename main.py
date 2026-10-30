import os
import threading
from flask import Flask
import bot

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run_bot():
    # This runs the bot directly without breaking the web server loop
    try:
        bot.main()
    except Exception as e:
        print(f"Bot crashed: {e}")

if __name__ == "__main__":
    # Start the bot in a separate thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start the web server (Render needs this to stay alive)
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
