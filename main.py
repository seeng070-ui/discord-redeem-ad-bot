import discord
from discord.ext import commands
import asyncio
import secrets

# Place your official Bot Token here from the Discord Developer Portal
TOKEN = "MTUyOTA4Njg5MzIzOTU2NjUwMQ.GWNeqa.A-4f0lzVE8rYC-MrDn46EWSRvtMSORUz5vRiLU"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Global variables for simple runtime memory storage
redeem_codes = set()       # Stores generated active keys
authorized_users = set()   # Stores User IDs of members who redeemed a code
user_configs = {}          # Maps User IDs to individual AdManager instances

class UserAdManager:
    def __init__(self, user_id):
        self.user_id = user_id
        self.channel_id = None
        self.message = "Default advertisement message. Use !setmessage to update."
        self.interval = 1800  # Default 30 minutes
        self.is_running = False

    async def start_loop(self):
        if self.is_running:
            return
        self.is_running = True
        
        while self.is_running:
            if self.channel_id:
                channel = bot.get_channel(self.channel_id)
                if channel:
                    try:
                        # Safely dispatches the user's custom campaign copy using the official bot client
                        await channel.send(f"📢 **Ad by <@{self.user_id}>:**\n{self.message}")
                    except Exception as e:
                        print(f"Error sending message for user {self.user_id}: {e}")
            await asyncio.sleep(self.interval)

    def stop_loop(self):
        self.is_running = False

def get_user_config(user_id):
    if user_id not in user_configs:
        user_configs[user_id] = UserAdManager(user_id)
    return user_configs[user_id]

@bot.event
async def on_ready():
    print(f"{bot.user.name} is online and running the premium system!")

# --- REDEEM CODE SYSTEM ---

# 1. Command to generate a code (Server Administrators Only)
@bot.command()
@commands.has_permissions(administrator=True)
async def generatecode(ctx):
    # Generates a random secure 8-character string
    code = secrets.token_hex(4).upper()
    redeem_codes.add(code)
    await ctx.send(f"🔑 **New Redeem Code Generated:** `{code}`\nUsers can claim access using `!redeem [code]`.")

# 2. Command for users to claim system authorization
@bot.command()
async def redeem(ctx, code: str):
    code = code.upper()
    if code in redeem_codes:
        redeem_codes.remove(code)  # Single-use enforcement
        authorized_users.add(ctx.author.id)
        await ctx.send(f"✅ Code applied! <@{ctx.author.id}>, you are now authorized to use the advertising suite.")
    else:
        await ctx.send("❌ Invalid or expired redeem code.")

# --- ADVERTISEMENT SUITE ---

# 3. Command to assign the target channel via ID
@bot.command()
async def setchannelid(ctx, channel_id: int):
    if ctx.author.id not in authorized_users:
        await ctx.send("❌ Access Denied. You must redeem a valid license key first.")
        return

    channel = bot.get_channel(channel_id)
    if not channel:
        await ctx.send("❌ Invalid Channel ID or the bot cannot access that channel.")
        return
        
    config = get_user_config(ctx.author.id)
    config.channel_id = channel_id
    await ctx.send(f"✅ Target channel updated to ID: {channel_id} ({channel.mention})")

# 4. Command to change ad message copy
@bot.command()
async def setmessage(ctx, *, new_msg: str):
    if ctx.author.id not in authorized_users:
        await ctx.send("❌ Access Denied.")
        return
    config = get_user_config(ctx.author.id)
    config.message = new_msg
    await ctx.send("✅ Your custom advertisement layout has been saved!")

# 5. Command to change interval timing (in minutes)
@bot.command()
async def settime(ctx, minutes: int):
    if ctx.author.id not in authorized_users:
        await ctx.send("❌ Access Denied.")
        return
    if minutes < 1:
        await ctx.send("❌ The posting frequency cannot be under 1 minute.")
        return
    config = get_user_config(ctx.author.id)
    config.interval = minutes * 60
    await ctx.send(f"⏱️ Your ad pacing updated to post every {minutes} minutes.")

# 6. Command to START individual loops
@bot.command()
async def start(ctx):
    if ctx.author.id not in authorized_users:
        await ctx.send("❌ Access Denied.")
        return
    config = get_user_config(ctx.author.id)
    if not config.channel_id:
        await ctx.send("❌ Please assign a valid target channel first using `!setchannelid [ID]`.")
        return
    if config.is_running:
        await ctx.send("ℹ️ Your automated campaign loop is already active.")
        return
    
    asyncio.create_task(config.start_loop())
    await ctx.send("🚀 Your automated advertisement loop has been successfully started!")

# 7. Command to STOP individual loops
@bot.command()
async def stop(ctx):
    if ctx.author.id not in authorized_users:
        await ctx.send("❌ Access Denied.")
        return
    config = get_user_config(ctx.author.id)
    if not config.is_running:
        await ctx.send("ℹ️ Your automated campaign loop is currently inactive.")
        return
    config.stop_loop()
    await ctx.send("🛑 Your automated advertisement loop has been stopped!")

# Catch basic permission failures cleanly
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ This command is restricted to server administrators.")

bot.run(TOKEN)
  
