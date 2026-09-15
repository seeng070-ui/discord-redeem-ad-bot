import discord
from discord.ext import commands, tasks
import secrets
import os

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
        self.message = "Default advertisement message. Use !setmessage to update."
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

# --- REDEEM CODE SYSTEM ---

@bot.command()
@commands.has_permissions(administrator=True)
async def generatecode(ctx):
    code = secrets.token_hex(4).upper()
    redeem_codes.add(code)
    await ctx.send(f"🔑 **New Redeem Code Generated:** `{code}`\nUsers can claim access using `!redeem [code]`.")

@bot.command()
async def redeem(ctx, code: str):
    code = code.upper()
    if code in redeem_codes:
        redeem_codes.remove(code)  
        authorized_users.add(ctx.author.id)
        await ctx.send(f"✅ Code applied! <@{ctx.author.id}>, you are now authorized to use the advertising suite.")
    else:
        await ctx.send("❌ Invalid or expired redeem code.")

# --- ADVERTISEMENT SUITE ---

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

@bot.command()
async def setmessage(ctx, *, new_msg: str):
    if ctx.author.id not in authorized_users:
        await ctx.send("❌ Access Denied.")
        return
    config = get_user_config(ctx.author.id)
    config.message = new_msg
    await ctx.send("✅ Your custom advertisement layout has been saved!")

@bot.command()
async def settime(ctx, minutes: int):
    if ctx.author.id not in authorized_users:
        await ctx.send("❌ Access Denied.")
        return
    if minutes < 1:
        await ctx.send("❌ The posting frequency cannot be under 1 minute.")
        return
    config = get_user_config(ctx.author.id)
    config.interval_minutes = minutes
    await ctx.send(f"⏱️ Your ad pacing updated to post every {minutes} minutes.")

@bot.command()
async def start(ctx):
    if ctx.author.id not in authorized_users:
        await ctx.send("❌ Access Denied.")
        return
    config = get_user_config(ctx.author.id)
    if not config.channel_id:
        await ctx.send("❌ Please assign a valid target channel first using `!setchannelid [ID]`.")
        return
    
    # Initialize and start the discord.py built-in background loop task
    config.task = config.setup_task()
    config.task.start()
    await ctx.send("🚀 Your automated advertisement loop has been successfully started!")

@bot.command()
async def stop(ctx):
    if ctx.author.id not in authorized_users:
        await ctx.send("❌ Access Denied.")
        return
    config = get_user_config(ctx.author.id)
    if not hasattr(config, 'task') or not config.task.is_running():
        await ctx.send("ℹ️ Your automated campaign loop is currently inactive.")
        return
    config.task.stop()
    await ctx.send("🛑 Your automated advertisement loop has been stopped!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ This command is restricted to server administrators.")

bot.run(TOKEN)
    
