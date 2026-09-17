import discord
from discord import app_commands
from discord.ext import tasks
import json
import os
import secrets
import requests
import time
from datetime import datetime, timezone

CONFIG_FILE = "config.json"

# ⚠️ PLACE YOUR NUMERIC DISCORD USER ID HERE
OWNER_USER_ID = 1495498780253094062 

# Duration mappings in seconds
DURATIONS = {
    "1d": 86400,          # 1 day
    "1w": 604800,         # 7 days
    "1m": 2592000,        # 30 days
    "lifetime": None      # No expiration
}

def load_config():
    """Loads configurations and migrates legacy structure if needed."""
    default = {
        "valid_keys": {},      # Format: {"KEY_STRING": duration_seconds or None}
        "redeemed_users": {}   # Format: {"user_id": {..., "expires_at": timestamp or None}}
    }
    
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(default, f, indent=4)
        return default

    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)

        # Migrate valid_keys if it was previously a list
        if isinstance(data.get("valid_keys"), list):
            data["valid_keys"] = {k: DURATIONS["1m"] for k in data["valid_keys"]}

        if not isinstance(data.get("redeemed_users"), dict):
            data["redeemed_users"] = {}

        return data
    except Exception:
        with open(CONFIG_FILE, "w") as f:
            json.dump(default, f, indent=4)
        return default

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def format_expiry(timestamp):
    if timestamp is None:
        return "Lifetime Access"
    if timestamp < time.time():
        return "Expired"
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

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

    @tasks.loop(seconds=5)
    async def ad_loop(self):
        config = load_config()
        current_time = time.time()
        config_changed = False
        
        if not isinstance(config.get("redeemed_users"), dict):
            return

        for user_id, user_data in config["redeemed_users"].items():
            # Check subscription expiration
            expires_at = user_data.get("expires_at")
            if expires_at is not None and current_time >= expires_at:
                if user_data.get("is_running"):
                    user_data["is_running"] = False
                    config_changed = True
                    print(f"[!] Plan expired for user {user_id}. Broadcast stopped.")
                continue

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
                url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
                try:
                    response = requests.post(url, json=payload, headers=headers)
                    if response.status_code in [200, 201]:
                        print(f"[✓] User {user_id} dispatched message to channel {channel_id}")
                    else:
                        print(f"[✗] User {user_id} transmission failed for channel {channel_id}: {response.status_code}")
                except Exception as e:
                    print(f"Error dispatching for user {user_id}: {e}")
            
            config["redeemed_users"][user_id]["last_sent"] = current_time
            config_changed = True
            
        if config_changed:
            save_config(config)

bot = AdvertiserBot()

def is_active(user_id, config):
    user_str = str(user_id)
    if user_str not in config["redeemed_users"]:
        return False
    
    expires_at = config["redeemed_users"][user_str].get("expires_at")
    if expires_at is None:
        return True
    return time.time() < expires_at

# ==================== DISCORD SLASH COMMANDS ====================

@bot.tree.command(name="generate-key", description="[OWNER ONLY] Generate a timed access key.")
@app_commands.describe(duration="Select the key validity duration")
@app_commands.choices(duration=[
    app_commands.Choice(name="1 Day", value="1d"),
    app_commands.Choice(name="1 Week", value="1w"),
    app_commands.Choice(name="1 Month (30 Days)", value="1m"),
    app_commands.Choice(name="Lifetime", value="lifetime"),
])
async def generate_key(interaction: discord.Interaction, duration: app_commands.Choice[str]):
    if interaction.user.id != OWNER_USER_ID:
        return await interaction.response.send_message("❌ Unauthorized access.", ephemeral=True)
    
    config = load_config()
    key = f"ADV-{secrets.token_hex(6).upper()}"
    duration_val = DURATIONS[duration.value]
    
    config["valid_keys"][key] = duration_val
    save_config(config)
    
    await interaction.response.send_message(
        f"🔑 **Key Created:** `{key}`\n**Plan Duration:** {duration.name}",
        ephemeral=True
    )

@bot.tree.command(name="redeem", description="Redeem an access key to activate or extend your plan.")
@app_commands.describe(key="Your license registration key")
async def redeem_key(interaction: discord.Interaction, key: str):
    config = load_config()
    user_id = str(interaction.user.id)
    current_time = time.time()

    if key not in config["valid_keys"]:
        return await interaction.response.send_message("❌ Invalid or expired license key.", ephemeral=True)
    
    duration = config["valid_keys"].pop(key)
    user_profile = config["redeemed_users"].get(user_id)

    # Initialize user profile if new
    if not user_profile:
        config["redeemed_users"][user_id] = {
            "token": "",
            "channels": [],
            "message": "Automated system broadcast placeholder text.",
            "interval": 60, 
            "last_sent": 0,
            "is_running": False,
            "expires_at": (current_time + duration) if duration else None
        }
    else:
        # Stack time on top of existing remaining time or upgrade to lifetime
        current_expiry = user_profile.get("expires_at")
        if duration is None:
            user_profile["expires_at"] = None
        elif current_expiry is None:
            pass  # Already on lifetime access
        elif current_expiry > current_time:
            user_profile["expires_at"] = current_expiry + duration
        else:
            user_profile["expires_at"] = current_time + duration

    save_config(config)
    expiry_text = format_expiry(config["redeemed_users"][user_id]["expires_at"])
    await interaction.response.send_message(
        f"✅ Key redeemed successfully!\n**Plan Expiry:** `{expiry_text}`\nUse `/set-token` and `/config` to finish setup.",
        ephemeral=True
    )

@bot.tree.command(name="status", description="Check your current subscription expiry and bot settings.")
async def status(interaction: discord.Interaction):
    config = load_config()
    user_id = str(interaction.user.id)

    if user_id not in config["redeemed_users"]:
        return await interaction.response.send_message("❌ No account found. Redeem a key first.", ephemeral=True)

    data = config["redeemed_users"][user_id]
    expiry_text = format_expiry(data.get("expires_at"))
    running = "🟢 Running" if data.get("is_running") else "🔴 Stopped"
    channels_count = len(data.get("channels", []))

    msg = (
        f"📋 **Subscription & Runtime Status**\n"
        f"• **Expiration:** `{expiry_text}`\n"
        f"• **Loop State:** {running}\n"
        f"• **Target Channels:** `{channels_count}` configured\n"
        f"• **Interval:** `{data.get('interval', 60)}s`\n"
        f"• **Token Linked:** `{'Yes' if data.get('token') else 'No'}`"
    )
    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="set-token", description="Configure your authorization token.")
@app_commands.describe(token="Your Discord account token")
async def set_token(interaction: discord.Interaction, token: str):
    config = load_config()
    user_id = str(interaction.user.id)
    
    if not is_active(user_id, config):
        return await interaction.response.send_message("🔒 Subscription inactive or expired. Redeem a key first.", ephemeral=True)
        
    config["redeemed_users"][user_id]["token"] = token.strip()
    save_config(config)
    await interaction.response.send_message("🔒 Token saved securely.", ephemeral=True)

@bot.tree.command(name="config", description="Configure transmission channels, message content, and frequency.")
@app_commands.describe(
    channels="Comma-separated channel Snowflake IDs", 
    text="Message text to broadcast",
    interval="Delay between cycles in seconds (min 10)"
)
async def setup_configs(
    interaction: discord.Interaction, 
    channels: str = None, 
    text: str = None,
    interval: int = None
):
    config = load_config()
    user_id = str(interaction.user.id)
    
    if not is_active(user_id, config):
        return await interaction.response.send_message("🔒 Subscription inactive or expired. Redeem a key first.", ephemeral=True)

    if channels: 
        config["redeemed_users"][user_id]["channels"] = [c.strip() for c in channels.split(",") if c.strip()]
    if text: 
        config["redeemed_users"][user_id]["message"] = text
    if interval is not None:
        if interval < 10: 
            return await interaction.response.send_message("⚠️ Interval cannot be lower than 10 seconds.", ephemeral=True)
        config["redeemed_users"][user_id]["interval"] = interval

    save_config(config)
    await interaction.response.send_message("⚙️ Configurations updated.", ephemeral=True)

@bot.tree.command(name="start", description="Start automated broadcasting.")
async def start_ad(interaction: discord.Interaction):
    config = load_config()
    user_id = str(interaction.user.id)
    
    if not is_active(user_id, config):
        return await interaction.response.send_message("🔒 Subscription inactive or expired. Redeem a key first.", ephemeral=True)

    user_profile = config["redeemed_users"][user_id]
    if not user_profile["token"] or not user_profile["channels"]:
        return await interaction.response.send_message("❌ Token or channel IDs are missing. Configure them first.", ephemeral=True)

    config["redeemed_users"][user_id]["is_running"] = True
    config["redeemed_users"][user_id]["last_sent"] = 0 
    save_config(config)
    await interaction.response.send_message("▶️ Transmission loop **STARTED**.")

@bot.tree.command(name="stop", description="Stop automated broadcasting.")
async def stop_ad(interaction: discord.Interaction):
    config = load_config()
    user_id = str(interaction.user.id)
    
    if user_id not in config["redeemed_users"]:
        return await interaction.response.send_message("❌ Account not found.", ephemeral=True)

    config["redeemed_users"][user_id]["is_running"] = False
    save_config(config)
    await interaction.response.send_message("🛑 Transmission loop **STOPPED**.", ephemeral=True)

# Replace with your actual bot token (store as an environment variable in production)
bot.run(os.getenv("BOT_TOKEN"))
