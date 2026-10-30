import os
import asyncio
import threading
from flask import Flask
import bot

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run_bot():
    # Create a new event loop for this specific background thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Run the bot inside this loop
    try:
        bot.main()
    except Exception as e:
        print(f"Bot crashed: {e}")

if __name__ == "__main__":
    # Start the bot in a separate thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start the Flask web server
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
