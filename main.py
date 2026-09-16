import discord
from discord import app_commands
import json
import os
import asyncio

# File to persist user configuration
DATA_FILE = "bot_data.json"

# List of authorized redeem codes
VALID_CODES = ["PREMIUM100", "STARTBOT2026", "ADVIP"]

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

class AdvertBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.active_tasks = {}
        # In-memory session tracking for message statistics
        self.stats = {} 

    async def setup_hook(self):
        await self.tree.sync()
        print("⚡ Slash Commands Successfully Synced Globally!")

bot = AdvertBot()

# Background loop executing the automated broadcasting
async def advertisement_loop(user_id, channel_id, interval_minutes, message_content):
    if user_id not in bot.stats:
        bot.stats[user_id] = {"sent_count": 0}
        
    while True:
        try:
            channel = bot.get_channel(int(channel_id)) or await bot.fetch_channel(int(channel_id))
            if channel:
                await channel.send(message_content)
                bot.stats[user_id]["sent_count"] += 1
                print(f"📢 Ad automatically sent for User {user_id} in Channel {channel_id}. Total: {bot.stats[user_id]['sent_count']}")
        except Exception as e:
            print(f"❌ Error sending ad for user {user_id}: {e}")
        
        await asyncio.sleep(interval_minutes * 60)

@bot.event
async def on_ready():
    print(f"🤖 Logged in successfully as {bot.user.name} ({bot.user.id})")
    
    # Auto-resume advertisement processes if bot restarts
    data = load_data()
    for user_id, config in data.items():
        if config.get("is_running") and config.get("config"):
            c = config["config"]
            task = bot.loop.create_task(
                advertisement_loop(user_id, c["channel_id"], c["interval"], c["message"])
            )
            bot.active_tasks[user_id] = task

# 1. Redeem Command
@bot.tree.command(name="redeem", description="Redeem your premium code to unlock features.")
@app_commands.describe(code="Enter your access code")
async def redeem(interaction: discord.Interaction, code: str):
    data = load_data()
    user_id = str(interaction.user.id)

    if code in VALID_CODES:
        if user_id not in data:
            data[user_id] = {"verified": True, "token": None, "config": {}, "is_running": False}
        else:
            data[user_id]["verified"] = True
        
        save_data(data)
        await interaction.response.send_message("✅ **Code redeemed successfully!** You now have access to advertisement features.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ **Invalid code.** Please provide a valid activation code.", ephemeral=True)

# 2. Set Token Command
@bot.tree.command(name="settoken", description="Securely save your user or application token.")
@app_commands.describe(token="Your secret Discord token")
async def set_token(interaction: discord.Interaction, token: str):
    data = load_data()
    user_id = str(interaction.user.id)

    if user_id not in data or not data[user_id].get("verified"):
        await interaction.response.send_message("🔒 Access Denied. Please use `/redeem` first.", ephemeral=True)
        return

    data[user_id]["token"] = token
    save_data(data)
    await interaction.response.send_message("🔑 **Token updated and secured successfully!**", ephemeral=True)

# 3. Config Command
@bot.tree.command(name="config", description="Configure your auto-advertisement parameters.")
@app_commands.describe(
    channel="Select the target channel",
    interval_minutes="Time delay between advertisements (in minutes)",
    message="The text message you want to advertise"
)
async def config(interaction: discord.Interaction, channel: discord.TextChannel, interval_minutes: int, message: str):
    data = load_data()
    user_id = str(interaction.user.id)

    if user_id not in data or not data[user_id].get("verified"):
        await interaction.response.send_message("🔒 Access Denied. Please use `/redeem` first.", ephemeral=True)
        return

    if interval_minutes < 1:
        await interaction.response.send_message("⚠️ The interval must be at least 1 minute.", ephemeral=True)
        return

    data[user_id]["config"] = {
        "channel_id": str(channel.id),
        "interval": interval_minutes,
        "message": message
    }
    save_data(data)
    
    await interaction.response.send_message(
        f"⚙️ **Configuration Successfully Saved!**\n"
        f"📍 **Target Channel:** {channel.mention}\n"
        f"⏱️ **Interval:** {interval_minutes} minute(s)\n"
        f"📝 **Message Layout:** {message}", 
        ephemeral=True
    )

# 4. Start Command
@bot.tree.command(name="start", description="Activate your automated advertisement broadcasting.")
async def start(interaction: discord.Interaction):
    data = load_data()
    user_id = str(interaction.user.id)

    if user_id not in data or not data[user_id].get("verified"):
        await interaction.response.send_message("🔒 Access Denied. Please use `/redeem` first.", ephemeral=True)
        return

    user_config = data[user_id].get("config")
    if not user_config:
        await interaction.response.send_message("⚠️ Configuration not found. Please run `/config` first.", ephemeral=True)
        return

    if user_id in bot.active_tasks:
        await interaction.response.send_message("ℹ️ Your advertisement system is already actively running.", ephemeral=True)
        return

    # Initialize or reset the local transmission counter metrics on start trigger
    bot.stats[user_id] = {"sent_count": 0}

    task = bot.loop.create_task(
        advertisement_loop(
            user_id, 
            user_config["channel_id"], 
            user_config["interval"], 
            user_config["message"]
        )
    )
    bot.active_tasks[user_id] = task
    
    data[user_id]["is_running"] = True
    save_data(data)

    await interaction.response.send_message("🚀 **Auto-advertisement schedule started successfully!**", ephemeral=True)

# 5. Stop Command
@bot.tree.command(name="stop", description="Suspend your active advertisement broadcasting.")
async def stop(interaction: discord.Interaction):
    data = load_data()
    user_id = str(interaction.user.id)

    if user_id not in bot.active_tasks:
        await interaction.response.send_message("ℹ️ You do not have any running advertisement processes right now.", ephemeral=True)
        return

    bot.active_tasks[user_id].cancel()
    del bot.active_tasks[user_id]

    data[user_id]["is_running"] = False
    save_data(data)

    await interaction.response.send_message("🛑 **Auto-advertisement broadcasting has been stopped.**", ephemeral=True)

# 6. Status Command
@bot.tree.command(name="status", description="Check your current advertisement layout and live engine status.")
async def status(interaction: discord.Interaction):
    data = load_data()
    user_id = str(interaction.user.id)

    if user_id not in data or not data[user_id].get("verified"):
        await interaction.response.send_message("🔒 Access Denied. Please use `/redeem` first.", ephemeral=True)
        return

    user_data = data[user_id]
    user_config = user_data.get("config", {})
    is_running = user_id in bot.active_tasks
    
    status_emoji = "🟢 RUNNING" if is_running else "🔴 STOPPED"
    channel_mention = f"<#{user_config['channel_id']}>" if "channel_id" in user_config else "Not Configured"
    interval = f"{user_config.get('interval')} minute(s)" if "interval" in user_config else "Not Configured"
    message_text = user_config.get("message", "Not Configured")
    
    # Retrieve messages sent count in the current session
    sent_count = bot.stats.get(user_id, {}).get("sent_count", 0) if is_running else 0

    status_embed = discord.Embed(title="📢 Auto-Advertiser Status Panel", color=discord.Color.blue())
    status_embed.add_field(name="⚙️ Engine Status", value=f"**{status_emoji}**", inline=False)
    status_embed.add_field(name="📍 Target Channel", value=channel_mention, inline=True)
    status_embed.add_field(name="⏱️ Interval Rate", value=interval, inline=True)
    status_embed.add_field(name="📊 Messages Sent (Current Session)", value=f"`{sent_count}` times", inline=False)
    status_embed.add_field(name="📝 Active Message Payload", value=f"```\n{message_text}\n```", inline=False)
    
    await interaction.response.send_message(embed=status_embed, ephemeral=True)

# Replace with your actual main application bot token
bot.run("YOUR_MAIN_BOT_TOKEN")
    
