import discord
from discord.ext import commands
from datetime import datetime, timezone
import os
import json
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────
TOKEN = os.getenv("DISCORD_TOKEN")  # Set your bot token as an env variable
TOTALS_FILE = "voice_totals.json"   # File to persist voice time data


# ── Persistence Helpers ───────────────────────────────────────────────────────
def load_totals() -> dict:
    """Load saved voice totals from disk. Keys are stored as strings in JSON."""
    if os.path.exists(TOTALS_FILE):
        with open(TOTALS_FILE, "r") as f:
            raw = json.load(f)
        return {int(k): v for k, v in raw.items()}  # convert keys back to int
    return {}


def save_totals(totals: dict) -> None:
    """Write voice totals to disk atomically — no corrupt file on crash."""
    tmp = TOTALS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump({str(k): v for k, v in totals.items()}, f, indent=2)
    os.replace(tmp, TOTALS_FILE)  # atomic swap


# ── Voice Tracking State ──────────────────────────────────────────────────────
# { user_id: join_timestamp }  — people currently in a voice channel
voice_sessions: dict[int, datetime] = {}

# { user_id: total_seconds }  — accumulated time, loaded from disk on startup
voice_totals: dict[int, float] = load_totals()

# ── Bot Setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
intents.voice_states = True     # Required to track voice channel events

bot = commands.Bot(command_prefix="!", intents=intents)


# ── Events ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

    # Scan all guilds for members already sitting in voice channels.
    # Without this, anyone in a call when the bot starts would never get
    # a join timestamp and their time wouldn't be counted.
    now = datetime.now(timezone.utc)
    already_in_vc = 0
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if not member.bot:
                    voice_sessions[member.id] = now
                    already_in_vc += 1

    print(f"📡 Scanning voice channels — found {already_in_vc} member(s) already in calls")
    print(f"💾 Loaded totals for {len(voice_totals)} member(s) from {TOTALS_FILE}")
    print("─" * 40)


@bot.event
async def on_member_join(member):
    """Greet new members in a 'general' channel if it exists."""
    channel = discord.utils.get(member.guild.text_channels, name="general")
    if channel:
        await channel.send(f"👋 Welcome to the server, {member.mention}!")


# ── Commands ──────────────────────────────────────────────────────────────────
@bot.command(name="ping")
async def ping(ctx):
    """Check bot latency."""
    await ctx.send(f"🏓 Pong! Latency: {round(bot.latency * 1000)}ms")


@bot.command(name="hello")
async def hello(ctx):
    """Say hello to the user."""
    await ctx.send(f"Hello, {ctx.author.mention}! 👋")


@bot.command(name="roll")
async def roll(ctx, sides: int = 6):
    """Roll a dice. Usage: !roll [sides]  (default: 6)"""
    import random
    if sides < 2:
        await ctx.send("❌ A dice needs at least 2 sides!")
        return
    result = random.randint(1, sides)
    await ctx.send(f"🎲 You rolled a **{result}** (d{sides})")


@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 5):
    """Delete messages. Usage: !clear [amount]  (default: 5, requires Manage Messages)"""
    if amount < 1 or amount > 100:
        await ctx.send("❌ Please specify a number between 1 and 100.")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include the command itself
    confirm = await ctx.send(f"🗑️ Deleted {len(deleted) - 1} message(s).")
    await confirm.delete(delay=3)


@bot.command(name="info")
async def info(ctx):
    """Show server info."""
    guild = ctx.guild
    embed = discord.Embed(title=f"📋 {guild.name}", color=discord.Color.blurple())
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Channels", value=len(guild.text_channels), inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%b %d, %Y"), inline=True)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await ctx.send(embed=embed)


# ── Voice Tracking ────────────────────────────────────────────────────────────
@bot.event
async def on_voice_state_update(member, before, after):
    """Track when members join or leave voice channels."""
    if member.bot:
        return  # ignore other bots

    now = datetime.now(timezone.utc)
    joined = before.channel is None and after.channel is not None
    left   = before.channel is not None and after.channel is None

    if joined:
        voice_sessions[member.id] = now

    elif left:
        if member.id in voice_sessions:
            elapsed = (now - voice_sessions.pop(member.id)).total_seconds()
            voice_totals[member.id] = voice_totals.get(member.id, 0) + elapsed
            save_totals(voice_totals)  # persist to disk every time someone leaves


def format_duration(seconds: float) -> str:
    """Convert seconds into a readable string like 2h 15m 30s."""
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    parts = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


@bot.command(name="voiceleaderboard", aliases=["vlb", "vc"])
async def voice_leaderboard(ctx, top: int = 10):
    """Show who has spent the most time in voice channels. Usage: !vlb [top N]"""
    now = datetime.now(timezone.utc)

    # Merge saved totals with time accrued in any currently active sessions
    combined: dict = dict(voice_totals)
    for user_id, join_time in voice_sessions.items():
        live_seconds = (now - join_time).total_seconds()
        combined[user_id] = combined.get(user_id, 0) + live_seconds

    if not combined:
        await ctx.send("📭 No voice activity recorded yet. Jump in a VC!")
        return

    sorted_users = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:top]

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (user_id, seconds) in enumerate(sorted_users):
        member = ctx.guild.get_member(user_id)
        name = member.display_name if member else f"Unknown ({user_id})"
        live = "🔴 " if user_id in voice_sessions else ""
        medal = medals[i] if i < 3 else f"`{i + 1}.`"
        lines.append(f"{medal} {live}**{name}** — {format_duration(seconds)}")

    embed = discord.Embed(
        title="🎙️ Voice Channel Leaderboard",
        description="\n".join(lines),
        color=discord.Color.blurple(),
        timestamp=now,
    )
    embed.set_footer(text="🔴 = currently in a voice channel")
    await ctx.send(embed=embed)


@bot.command(name="mytime")
async def my_time(ctx):
    """Check your own total voice time. Usage: !mytime"""
    now = datetime.now(timezone.utc)
    user_id = ctx.author.id

    total = voice_totals.get(user_id, 0)
    if user_id in voice_sessions:
        total += (now - voice_sessions[user_id]).total_seconds()

    if total == 0:
        await ctx.send(f"⏱️ {ctx.author.mention} You haven't spent any time in voice yet!")
    else:
        await ctx.send(f"⏱️ {ctx.author.mention} You've spent **{format_duration(total)}** in voice channels.")


@bot.command(name="resetvc")
@commands.has_permissions(administrator=True)
async def reset_vc(ctx):
    """Reset all voice time stats. Admins only. Usage: !resetvc"""
    voice_totals.clear()
    voice_sessions.clear()
    save_totals(voice_totals)
    await ctx.send("🗑️ Voice leaderboard has been reset.")


# ── Error Handling ─────────────────────────────────────────────────────────────
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument. Check `!help` for usage.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Silently ignore unknown commands
    else:
        raise error


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is not set.")
    bot.run(TOKEN)