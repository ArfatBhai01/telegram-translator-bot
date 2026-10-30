import os
import threading
from flask import Flask
import bot  # This imports your existing bot.py

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_bot():
    # This runs your bot's main function
    bot.main()

if __name__ == "__main__":
    # Start the bot in a separate thread
    threading.Thread(target=run_bot).start()
    # Start the web server on the port Render provides
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)