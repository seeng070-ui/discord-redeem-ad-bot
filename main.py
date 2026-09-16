import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
from flask import Flask
from threading import Thread

# --- FLASK BACKGROUND SERVER FOR RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

Thread(target=run_flask).start()

# --- DISCORD BOT SETUP ---
TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

user_configs = {}

class UserAdManager:
    def __init__(self, user_id):
        self.user_id = user_id
        self.channel_id = None
        self.message = "Default advertisement message. Use /setmessage to change!"
        self.interval_minutes = 30
        self.ad_loop = None

    def start_task(self):
        if self.ad_loop and self.ad_loop.is_running():
            self.ad_loop.stop()

        @tasks.loop(minutes=self.interval_minutes)
        async def run_ad():
            if self.channel_id:
                channel = bot.get_channel(self.channel_id)
                if channel:
                    try:
                        await channel.send(f"📢 **Ad by <@{self.user_id}>:**\n{self.message}")
                    except Exception as e:
                        print(f"Error sending ad: {e}")

        self.ad_loop = run_ad
        self.ad_loop.start()

def get_user_config(user_id):
    if user_id not in user_configs:
        user_configs[user_id] = UserAdManager(user_id)
    return user_configs[user_id]

# --- SYNCHRONIZE SLASH COMMANDS ---
@bot.event
async def on_ready():
    print(f"{bot.user.name} is online!")
    try:
        # Pushes your / commands straight to Discord's servers
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# --- TRUE SLASH COMMANDS ---
@bot.tree.command(name="setchannel", description="Set the current text channel for your advertisements.")
async def setchannel(interaction: discord.Interaction):
    config = get_user_config(interaction.user.id)
    config.channel_id = interaction.channel_id
    await interaction.response.send_message(f"✅ Advertising channel set to {interaction.channel.mention}!")

@bot.tree.command(name="setmessage", description="Set your custom advertisement message text.")
@app_commands.describe(msg="Your advertisement text layout")
async def setmessage(interaction: discord.Interaction, msg: str):
    config = get_user_config(interaction.user.id)
    config.message = msg
    await interaction.response.send_message("✅ Your advertisement text has been saved successfully!")

@bot.tree.command(name="startadv", description="Kick off the automated recurring advertising timer.")
async def startadv(interaction: discord.Interaction):
    config = get_user_config(interaction.user.id)
    if not config.channel_id:
        await interaction.response.send_message("❌ Set an advertising channel first using `/setchannel`!", ephemeral=True)
        return
    
    config.start_task()
    await interaction.response.send_message(f"🚀 Auto-advertising started! Posting every {config.interval_minutes} minutes.")

bot.run(TOKEN)
