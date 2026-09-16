import discord
from discord import app_commands
import os
import json
import asyncio
import requests
import secrets

CONFIG_FILE = "slash_bot_config.json"
# 🔴 IMPORTANT: Replace this with your exact personal Discord User ID
BOT_OWNER_ID = 123456789012345678  

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"redeem_codes": [], "users": {}}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

config_data = load_config()
active_loops = {}

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("[✓] Slash commands synced globally!")

    async def on_ready(self):
        print(f'[✓] Logged in as {self.user}')

bot = MyBot()

def check_premium(user_id: str):
    user_settings = config_data["users"].get(user_id, {})
    return user_settings.get("premium", False)

# Advertisement sender background task loop
async def run_ad_sender(user_id, channel_id, token, message, interval):
    url = f"https://discord.com{channel_id}/messages"
    headers = {"Authorization": token, "Content-Type": "application/json"}
    payload = {"content": message}

    while active_loops.get(user_id):
        try:
            response = await asyncio.to_thread(requests.post, url, json=payload, headers=headers)
            if response.status_code == 200:
                print(f"[+] Advertisement sent successfully for User {user_id}")
            elif response.status_code == 401:
                print(f"[!] Invalid Token for User {user_id}. Loop stopped automatically.")
                active_loops[user_id] = False
                break
        except Exception as e:
            print(f"[!] Error broadcasting advertisement: {e}")
        
        # Sleeps in 1-second chunks so that the stop command reacts instantly
        for _ in range(int(interval)):
            if not active_loops.get(user_id):
                break
            await asyncio.sleep(1)

# 1. GENERATE CODE (Owners Only)
@bot.tree.command(name="generate_code", description="[OWNER ONLY] Generate a new premium license redeem code.")
async def generate_code(interaction: discord.Interaction):
    if interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ This command can only be executed by the Bot Owner!", ephemeral=True)
        return

    new_code = f"ADS-{secrets.token_hex(4).upper()}"
    config_data["redeem_codes"].append(new_code)
    save_config(config_data)
    await interaction.response.send_message(
        f"✅ **New key generated successfully:**\n`{new_code}`\n\nUsers can claim this using `/redeem`.", 
        ephemeral=True
    )

# 2. REDEEM CODE
@bot.tree.command(name="redeem", description="Redeem a valid license code to unlock premium advertising features.")
@app_commands.describe(code="Your premium redeem code")
async def redeem(interaction: discord.Interaction, code: str):
    user_id = str(interaction.user.id)
    
    if check_premium(user_id):
        await interaction.response.send_message("❌ You are already a premium member!", ephemeral=True)
        return

    if code in config_data["redeem_codes"]:
        config_data["redeem_codes"].remove(code) # Key gets removed once claimed
        if user_id not in config_data["users"]:
            config_data["users"][user_id] = {}
        
        config_data["users"][user_id]["premium"] = True
        save_config(config_data)
        await interaction.response.send_message("🎉 **Congratulations!** Your code has been successfully redeemed. You can now use config settings.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Invalid or expired redeem code. Please double-check and try again.", ephemeral=True)

# 3. SET TOKEN
@bot.tree.command(name="set_token", description="Configure your personal Discord Account Token (Not a Bot Token).")
@app_commands.describe(token="Your Discord User Token")
async def set_token(interaction: discord.Interaction, token: str):
    user_id = str(interaction.user.id)
    if not check_premium(user_id):
        await interaction.response.send_message("🔒 Access Denied. Please run `/redeem` to unlock this system first.", ephemeral=True)
        return

    if user_id not in config_data["users"]:
        config_data["users"][user_id] = {}
        
    config_data["users"][user_id]["token"] = token
    save_config(config_data)
    await interaction.response.send_message("✅ Your account token has been updated and securely stored!", ephemeral=True)

# 4. CONFIG
@bot.tree.command(name="config", description="Configure the channel, time loop interval, and message body for your ads.")
@app_commands.describe(
    channel_id="The target Channel ID where advertisements should be sent",
    interval_seconds="Delay timeline threshold between transmissions (in seconds)",
    message="The body content text of your advertisement"
)
async def config(interaction: discord.Interaction, channel_id: str, interval_seconds: int, message: str):
    user_id = str(interaction.user.id)
    if not check_premium(user_id):
        await interaction.response.send_message("🔒 Access Denied. Please run `/redeem` first.", ephemeral=True)
        return

    if user_id not in config_data["users"] or "token" not in config_data["users"][user_id]:
        await interaction.response.send_message("❌ Please set your account token via `/set_token` before saving configurations.", ephemeral=True)
        return

    config_data["users"][user_id]["channel_id"] = channel_id
    config_data["users"][user_id]["interval"] = interval_seconds
    config_data["users"][user_id]["message"] = message
    save_config(config_data)

    await interaction.response.send_message(
        f"✅ **Configuration Matrix Updated!**\n"
        f"• **Channel ID:** `{channel_id}`\n"
        f"• **Interval Loop:** `{interval_seconds}` seconds\n"
        f"• **Ad Text Content:** `{message}`", 
        ephemeral=True
    )

# 5. START
@bot.tree.command(name="start", description="Activate the automated advertisement sender loop.")
async def start(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if not check_premium(user_id):
        await interaction.response.send_message("🔒 Access Denied.", ephemeral=True)
        return

    if active_loops.get(user_id):
        await interaction.response.send_message("⚠️ Your advertisement broadcaster is already running!", ephemeral=True)
        return

    user_settings = config_data["users"].get(user_id, {})
    token = user_settings.get("token")
    channel_id = user_settings.get("channel_id")
    interval = user_settings.get("interval")
    message = user_settings.get("message")

    if not all([token, channel_id, interval, message]):
        await interaction.response.send_message("❌ Configuration setup incomplete. Check token and `/config` settings before launching.", ephemeral=True)
        return

    active_loops[user_id] = True
    bot.loop.create_task(run_ad_sender(user_id, channel_id, token, message, interval))
    await interaction.response.send_message("🚀 **Auto-Advertiser Activated!** Your custom ad sequence will now begin broadcasting.", ephemeral=True)

# 6. STOP
@bot.tree.command(name="stop", description="Immediately terminate your running automated advertisement stream.")
async def stop(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    
    if not check_premium(user_id):
        await interaction.response.send_message("🔒 Access Denied.", ephemeral=True)
        return

    if not active_loops.get(user_id):
        await interaction.response.send_message("⚠️ Your auto-advertiser sequence is not active right now.", ephemeral=True)
        return

    active_loops[user_id] = False
    await interaction.response.send_message("🛑 **Auto-Advertiser Terminated Successfully.** No further messages will be dispatched.", ephemeral=True)

# 7. STATUS
@bot.tree.command(name="status", description="Query current configuration values and operational loop runtime states.")
async def status(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    is_prem = check_premium(user_id)
    
    if not is_prem:
        await interaction.response.send_message("📊 **License Status:** Basic Tier (Not Premium). Please activate using a token key.", ephemeral=True)
        return

    user_settings = config_data["users"].get(user_id, {})
    bot_status = "RUNNING 🟢" if active_loops.get(user_id) else "STOPPED 🔴"
    
    has_token = "Configured [✓]" if user_settings.get("token") else "Missing [✗]"
    channel = user_settings.get("channel_id", "Not set")
    interval = user_settings.get("interval", "Not set")
    msg = user_settings.get("message", "Not set")

    status_embed = (
        f"📊 **Broadcaster Engine Status:** {bot_status}\n\n"
        f"• **Account User Token:** {has_token}\n"
        f"• **Destination Channel ID:** `{channel}`\n"
        f"• **Time Interval Loop:** {interval} seconds\n"
        f"• **Active Payload Content:** `{msg}`"
    )
    await interaction.response.send_message(status_embed, ephemeral=True)

# Place your central Bot Token application credential down here
bot.run("YOUR_BOT_TOKEN_HERE")
                  
