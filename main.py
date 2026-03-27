import discord
from discord.ext import commands
import os, sys  
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────
TOKEN = os.getenv("DISCORD_TOKEN")

TRUSTED_USERS = set(
    int(uid.strip())
    for uid in os.getenv("TRUSTED_USERS", "").split(",")
    if uid.strip().isdigit()
)

# ── Bot Setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states    = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ── Error Handling ────────────────────────────────────────────────────────────
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument. Check `!help` for usage.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        raise error


async def load_cogs():
  
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and filename != "__init__.py":
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f"✅ Succesfully loaded {filename} cog")
            except:
                print(f"❌ Couldn't load {filename} cog")
                print(f"ERROR: {sys.exc_info()[0]}")
    

if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is not set.")
    
    bot.setup_hook = load_cogs
    bot.run(TOKEN)
