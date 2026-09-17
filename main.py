import discord
from discord import app_commands
from discord.ext import tasks
import json
import os
import secrets
import requests
import time

CONFIG_FILE = "config.json"

# ⚠️ PLACE YOUR PERSONAL NUMERIC DISCORD USER ID HERE (No quotes)
OWNER_USER_ID = 1448510941057646593

def load_config():
    """Loads setup configurations and automatically fixes structural bugs."""
    default = {
        "valid_keys": [],
        "redeemed_users": {}  
    }
    
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(default, f, indent=4)
        return default

    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            
        if not isinstance(data.get("redeemed_users"), dict):
            print("[!] Warning: Structural error detected in config.json. Resetting data format...")
            data["redeemed_users"] = {}
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=4)
        return data
    except Exception:
        with open(CONFIG_FILE, "w") as f:
            json.dump(default, f, indent=4)
        return default

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

class AdvertiserBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("[✓] Slash commands synced globally.")

    async def on_ready(self):
        print(f"[✓] Logged in as: {self.user}")
        if not self.ad_loop.is_running():
            self.ad_loop.start()

    # Dynamic Multi-User Advertising Execution Engine (Evaluates queue every 5 seconds)
    @tasks.loop(seconds=5)
    async def ad_loop(self):
        config = load_config()
        current_time = time.time()
        config_changed = False
        
        if not isinstance(config.get("redeemed_users"), dict):
            return

        for user_id, user_data in config["redeemed_users"].items():
            if not user_data.get("is_running") or not user_data.get("token") or not user_data.get("channels"):
                continue
            
            last_sent = user_data.get("last_sent", 0)
            user_interval = user_data.get("interval", 60) 
            
            if current_time - last_sent < user_interval:
                continue 
                
            headers = {
                "Authorization": user_data["token"],
                "Content-Type": "application/json"
            }
            payload = {"content": user_data["message"]}
            
            for channel_id in user_data["channels"]:
                url = f"https://discord.com{channel_id}/messages"
                try:
                    response = requests.post(url, json=payload, headers=headers)
                    if response.status_code in [200, 201, 204]:
                        print(f"[✓] User {user_id} dispatched message to channel {channel_id}")
                    else:
                        print(f"[✗] User {user_id} transmission failed for channel {channel_id}: {response.status_code}")
                except Exception as e:
                    print(f"Error handling live dispatch routine for user {user_id}: {e}")
            
            config["redeemed_users"][user_id]["last_sent"] = current_time
            config_changed = True
            
        if config_changed:
            save_config(config)

bot = AdvertiserBot()

def is_verified(user_id, config):
    return str(user_id) in config["redeemed_users"]

# ==================== DISCORD SLASH COMMAND INTERFACES ====================

@bot.tree.command(name="generate-key", description="[OWNER ONLY] Generate a premium authentication access validation key.")
async def generate_key(interaction: discord.Interaction):
    if interaction.user.id != OWNER_USER_ID:
        return await interaction.response.send_message("❌ ⚠️ Access Denied: Unauthorized client query.", ephemeral=True)
    
    config = load_config()
    new_key = f"ADV-{secrets.token_hex(6).upper()}"
    
    config["valid_keys"].append(new_key)
    save_config(config)
    
    await interaction.response.send_message(f"🔑 **New Key Generated:** `{new_key}`\nProvide this key to a customer to unlock their instance registry slot.", ephemeral=True)

@bot.tree.command(name="redeem", description="Consume a premium validation license key to unlock bot runtime controls.")
async def redeem_key(interaction: discord.Interaction, key: str):
    config = load_config()
    user_id = str(interaction.user.id)
    
    if user_id in config["redeemed_users"]:
        return await interaction.response.send_message("💡 Core profile configuration allocation is already configured on this account.", ephemeral=True)
        
    if key in config["valid_keys"]:
        config["valid_keys"].remove(key)
        config["redeemed_users"][user_id] = {
            "token": "",
            "channels": [],
            "message": "Automated system broadcast placeholder text.",
            "interval": 60, 
            "last_sent": 0,
            "is_running": False
        }
        save_config(config)
        await interaction.response.send_message("✅ Registry access slot initialized. Use `/set-token` to link your account transmission parameters.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Invalid or expired license registration key payload verified.", ephemeral=True)

@bot.tree.command(name="set-token", description="Configure your secure raw personal user runtime account access string.")
@app_commands.describe(token="Your Discord User Token")
async def set_token(interaction: discord.Interaction, token: str):
    config = load_config()
    user_id = str(interaction.user.id)
    
    if not is_verified(user_id, config):
        return await interaction.response.send_message("🔒 Access Denied. Process a key validation setup through `/redeem` first.", ephemeral=True)
        
    config["redeemed_users"][user_id]["token"] = token.strip()
    save_config(config)
    await interaction.response.send_message("🔒 **Transmission credentials verified and isolated safely inside internal registry.**", ephemeral=True)

@bot.tree.command(name="config", description="Configure routing destinations, message content payloads, and interval timing parameters.")
@app_commands.describe(
    channels="Target channel Snowflake IDs separated by commas", 
    text="The message markdown text copy template to broadcast",
    interval="Message frequency wait delay parameter (in seconds - e.g., 300 for 5 minutes)"
)
async def setup_configs(
    interaction: discord.Interaction, 
    channels: str = None, 
    text: str = None,
    interval: int = None
):
    config = load_config()
    user_id = str(interaction.user.id)
    
    if not is_verified(user_id, config):
        return await interaction.response.send_message("🔒 Access Denied. Register active status utilizing `/redeem` first.", ephemeral=True)

    if channels: 
        config["redeemed_users"][user_id]["channels"] = [c.strip() for c in channels.split(",") if c.strip()]
    if text: 
        config["redeemed_users"][user_id]["message"] = text
    if interval is not None:
        if interval < 10: 
            return await interaction.response.send_message("⚠️ For your safety, the interval duration cannot be lower than 10 seconds.", ephemeral=True)
        config["redeemed_users"][user_id]["interval"] = interval

    save_config(config)
    await interaction.response.send_message("⚙️ User configurations successfully updated and saved locally.", ephemeral=True)

@bot.tree.command(name="start", description="Activate continuous background broadcast loops.")
async def start_ad(interaction: discord.Interaction):
    config = load_config()
    user_id = str(interaction.user.id)
    
    if not is_verified(user_id, config):
        return await interaction.response.send_message("🔒 Access Denied. Register your instance access first.", ephemeral=True)

    user_profile = config["redeemed_users"][user_id]
    if not user_profile["token"] or not user_profile["channels"]:
        return await interaction.response.send_message("❌ Configurations incomplete. Set your channel routing configurations first.", ephemeral=True)

    config["redeemed_users"][user_id]["is_running"] = True
    config["redeemed_users"][user_id]["last_sent"] = 0 
    save_config(config)
    await interaction.response.send_message("▶️ Automatic transmission background loop engine **STARTED**.")

@bot.tree.command(name="stop", description="Suspend continuous runtime broadcast loops.")
async def stop_ad(interaction: discord.Interaction):
    config = load_config()
    user_id = str(interaction.user.id)
    
    if not is_verified(user_id, config):
        return await interaction.response.send_message("🔒 Access Denied. Register your structural instance space first.", ephemeral=True)

    config["redeemed_users"][user_id]["is_running"] = False
    save_config(config)
    await interaction.response.send_message("🛑 Automatic transmission background loop engine **STOPPED**.", ephemeral=True)

# ==================== RUN THE BOT CLIENT ====================
# Safely pulls the token from the BOT_TOKEN system environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("[✗] Error: BOT_TOKEN variable not found in system environment configurations.")
else:
    bot.run(BOT_TOKEN)
                        
