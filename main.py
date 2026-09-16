import discord
from discord.ext import commands, tasks
import secrets
import os
from flask import Flask
from threading import Thread

# --- FLASK BACKGROUND SERVER FOR RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    # Binds to Render's required port so the app doesn't shut down
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# Starts the fake website in a background thread
Thread(target=run_flask).start()

# --- DISCORD BOT SETUP ---
# Securely pulls token from Render's Environment settings
TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Global variables for runtime memory storage
redeem_codes = set()
authorized_users = set()
user_configs = {}

class UserAdManager:
    def __init__(self, user_id):
        self.user_id = user_id
        self.channel_id = None
        self.message = "Default advertisement message. Use !setmessage to change!"
        self.interval_minutes = 30  # Default 30 minutes

    # Using discord.ext.tasks instead of asyncio loops for stable cloud hosting
    def setup_task(self):
        @tasks.loop(minutes=self.interval_minutes)
        async def ad_loop():
            if self.channel_id:
                channel = bot.get_channel(self.channel_id)
                if channel:
                    try:
                        await channel.send(f"📢 **Ad by <@{self.user_id}>:**\n{self.message}")
                    except Exception as e:
                        print(f"Error sending message: {e}")
        return ad_loop

def get_user_config(user_id):
    if user_id not in user_configs:
        user_configs[user_id] = UserAdManager(user_id)
    return user_configs[user_id]

@bot.event
async def on_ready():
    print(f"{bot.user.name} is online and running the premium system!")

# --- COMMANDS ---
@bot.command()
async def setchannel(ctx):
    config = get_user_config(ctx.author.id)
    config.channel_id = ctx.channel.id
    await ctx.send(f"✅ Advertising channel set to {ctx.channel.mention} for this server slot!")

@bot.command()
async def setmessage(ctx, *, msg: str):
    config = get_user_config(ctx.author.id)
    config.message = msg
    await ctx.send("✅ Your advertisement text has been saved successfully!")

@bot.command()
async def startadv(ctx):
    config = get_user_config(ctx.author.id)
    if not config.channel_id:
        await ctx.send("❌ Please set an advertising channel first using `!setchannel`!")
        return
    
    # Initialize and kick off the automated loop
    loop_task = config.setup_task()
    loop_task.start()
    await ctx.send(f"🚀 Auto-advertising started! Posting every {config.interval_minutes} minutes.")

# --- THE CRITICAL MISSING RUNNER LINE ---
# This uses the token variable to officially bring the bot online on Discord
bot.run(TOKEN)
