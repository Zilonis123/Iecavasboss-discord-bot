from discord.ext import commands
import os
from datetime import datetime, timezone
import json
import discord
from zoneinfo import ZoneInfo

TRUSTED_USERS = set(
    int(uid.strip())
    for uid in os.getenv("TRUSTED_USERS", "").split(",")
    if uid.strip().isdigit()
)
TOTALS_FILE     = "voice_totals.json"       # all-time totals
BESTS_FILE      = "voice_bests.json"        # personal best single sessions

def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    parts = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)

def combined_totals(now: datetime) -> dict:
    """Merge saved totals with live session time."""
    result = dict(voice_totals)
    for uid, join_time in voice_sessions.items():
        result[uid] = result.get(uid, 0) + (now - join_time).total_seconds()
    return result



def _load(path: str, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default

def _save(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

def load_totals() -> dict:
    raw = _load(TOTALS_FILE, {})
    return {int(k): v for k, v in raw.items()}

def save_totals(totals: dict) -> None:
    _save(TOTALS_FILE, {str(k): v for k, v in totals.items()})

def load_bests() -> dict:
    raw = _load(BESTS_FILE, {})
    return {int(k): v for k, v in raw.items()}

def save_bests(bests: dict) -> None:
    _save(BESTS_FILE, {str(k): v for k, v in bests.items()})



# ----- streaks
TIMEZONE   = ZoneInfo("Europe/Riga")
STREAKS_FILE = "voice_streaks.json"
 
def load_streaks() -> dict:
    raw = _load(STREAKS_FILE, {})
    # Each entry: { "streak": int, "last_day": "YYYY-MM-DD" }
    return {int(k): v for k, v in raw.items()}
 
def save_streaks(streaks: dict) -> None:
    _save(STREAKS_FILE, {str(k): v for k, v in streaks.items()})
 
voice_streaks: dict[int, dict] = load_streaks()
 
def _update_streak(user_id: int) -> None:
    """Mark today as an active VC day and update the user's streak."""
    today = datetime.now(TIMEZONE).date().isoformat()
    entry = voice_streaks.get(user_id, {"streak": 0, "last_day": None})
 
    if entry["last_day"] == today:
        return  # already counted today, nothing to do
 
    from datetime import date, timedelta
    yesterday = (datetime.now(TIMEZONE).date() - timedelta(days=1)).isoformat()
 
    if entry["last_day"] == yesterday:
        print(f"{user_id} is on a {entry['streak']+1} streak")
        entry["streak"] += 1       # continued streak
    else:
        entry["streak"] = 1        # streak broken or first ever day
 
    entry["last_day"] = today
    voice_streaks[user_id] = entry
    save_streaks(voice_streaks)
    return entry["streak"]

def checkpoint_voice(user_id: int) -> float:
    """
    Flush a live session's elapsed time into voice_totals and voice_bests
    as if the user left, but keep them in voice_sessions so tracking continues.
    Returns the seconds added, or 0 if the user isn't in a session.
    """
    if user_id not in voice_sessions:
        return 0.0
 
    now     = datetime.now(timezone.utc)
    elapsed = (now - voice_sessions[user_id]).total_seconds()
 
    voice_totals[user_id] = voice_totals.get(user_id, 0) + elapsed
    if elapsed > voice_bests.get(user_id, 0):
        voice_bests[user_id] = elapsed
 
    # Reset the session start to now so time isn't double-counted next checkpoint
    voice_sessions[user_id] = now
    
    save_totals(voice_totals)
    save_bests(voice_bests)

    return elapsed

def checkpoint_all() -> int:
    """Checkpoint every active session. Returns number of users flushed."""
    for user_id in list(voice_sessions):
        checkpoint_voice(user_id)
    return len(voice_sessions)

voice_sessions: dict[int, datetime] = {}
voice_totals:   dict[int, float]    = load_totals()
voice_bests:    dict[int, float]    = load_bests()



# -----------------------------------

class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="vcsession", aliases=["vcs", "session", "s"])
    async def vc_session(self, ctx, member: discord.Member = None):
        """Show how long your current VC session has been. Usage: !vcsession [@user]"""
        target = member or ctx.author
    
        if target.id not in voice_sessions:
            who = "You're" if target == ctx.author else f"{target.display_name} is"
            await ctx.send(f"🔇 {who} not currently in a voice channel.")
            return
    
        elapsed = (datetime.now(timezone.utc) - voice_sessions[target.id]).total_seconds()
        pb      = voice_bests.get(target.id, 0)
        pct     = (elapsed / pb * 100) if pb > 0 else 0
        if pct > 100:
            pct = 100
    
        embed = discord.Embed(
            title=f"🎙️ {target.display_name}'s Current Session",
            color=discord.Color.green(),
        )
        embed.add_field(name="Session Time", value=format_duration(elapsed), inline=True)
        embed.add_field(name="Personal Best", value=format_duration(pb),     inline=True)
        if pb > 0:
            bar   = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
            label = "🏆 New PB in progress!" if elapsed > pb else f"{pct:.0f}% of PB"
            embed.add_field(name=label, value=f"`{bar}`", inline=False)
    
        await ctx.send(embed=embed)


    @commands.command("vcstreak", aliases=["streak", "vstreak"])
    async def vc_streak(self, ctx, member: discord.Member = None):
        """Show VC streak — consecutive days someone has been in a voice channel. Usage: !vcstreak [@user]"""
        target = member or ctx.author
        entry  = voice_streaks.get(target.id, {"streak": 0, "last_day": None})
        streak = entry["streak"]
        last   = entry["last_day"]
    
        today     = datetime.now(TIMEZONE).date().isoformat()
        from datetime import timedelta
        yesterday = (datetime.now(TIMEZONE).date() - timedelta(days=1)).isoformat()
    
        if streak == 0:
            await ctx.send(f"📭 {target.display_name} has no streak yet.")
            return
    
        # Warn if the streak is at risk (last active day was yesterday, not today)
        at_risk = last == yesterday and target.id not in voice_sessions
        broken  = last not in (today, yesterday)
    
        if broken:
            embed = discord.Embed(
                title=f"💀 {target.display_name}'s Streak — BROKEN",
                description=f"Their {streak}-day streak ended. Last seen **{last}**.",
                color=discord.Color.red(),
            )
        else:
            flames = "🔥" * min(streak, 10)
            title  = f"{flames} {target.display_name}'s Streak"
            desc   = f"**{streak} day{'s' if streak != 1 else ''}** in a row"
            if at_risk:
                desc += "\n\n⚠️ **At risk!** They haven't joined a VC today yet."
    
            embed = discord.Embed(title=title, description=desc, color=discord.Color.orange())
            embed.set_footer(text=f"Last active: {last}")
    
        await ctx.send(embed=embed)
    
    
    @commands.command(name="vcstreakboard", aliases=["streakboard", "streaklb"])
    async def vc_streak_board(self, ctx, top: int = 10):
        """Show the streak leaderboard. Usage: !vcstreakboard [top N]"""
        today     = datetime.now(TIMEZONE).date().isoformat()
        from datetime import timedelta
        yesterday = (datetime.now(TIMEZONE).date() - timedelta(days=1)).isoformat()
    
        active = {
            uid: e for uid, e in voice_streaks.items()
            if e["streak"] > 0 and e["last_day"] in (today, yesterday)
        }
    
        if not active:
            await ctx.send("📭 Nobody has an active streak right now.")
            return
    
        sorted_streaks = sorted(active.items(), key=lambda x: x[1]["streak"], reverse=True)[:top]
        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for i, (uid, entry) in enumerate(sorted_streaks):
            m      = ctx.guild.get_member(uid)
            name   = m.display_name if m else f"Unknown ({uid})"
            medal  = medals[i] if i < 3 else f"`{i + 1}.`"
            risk   = " ⚠️" if entry["last_day"] == yesterday and uid not in voice_sessions else ""
            flames = "🔥" * min(entry["streak"], 5)
            lines.append(f"{medal} **{name}** — {entry['streak']} days {flames}{risk}")
    
        embed = discord.Embed(
            title="🔥 VC Streak Leaderboard",
            description="\n".join(lines),
            color=discord.Color.orange(),
        )
        embed.set_footer(text="⚠️ = streak at risk, hasn't joined today yet")
        await ctx.send(embed=embed)



    @commands.command(name="resetvc", aliases=["rvc", "resvc"])
    @commands.has_permissions(administrator=True)
    async def reset_vc(self, ctx):
        if ctx.author.id not in TRUSTED_USERS:
            await ctx.send("🚫 You're not allowed to use this command.")
            return
        voice_totals.clear()
        voice_sessions.clear()
        voice_bests.clear()
        save_totals(voice_totals)
        save_bests(voice_bests)
        await ctx.send("🗑️ Voice leaderboard and personal bests have been reset.")


    @commands.command(name="voiceleaderboard", aliases=["vclb", "voicelb"])
    async def voice_leaderboard(self, ctx, top: int = 10):
        """Show all-time voice leaderboard. Usage: !vlb [top N]"""
        now  = datetime.now(timezone.utc)
        data = combined_totals(now)

        if not data:
            await ctx.send("📭 No voice activity recorded yet. Jump in a VC!")
            return

        sorted_users = sorted(data.items(), key=lambda x: x[1], reverse=True)[:top]
        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for i, (uid, secs) in enumerate(sorted_users):
            m = ctx.guild.get_member(uid)
            name = m.display_name if m else f"Unknown ({uid})"
            live = "🟢 " if uid in voice_sessions else "🔴 "
            medal = medals[i] if i < 3 else f"`{i + 1}.`"
            lines.append(f"{medal} {live}**{name}** — {format_duration(secs)}")

        embed = discord.Embed(
            title="🎙️ Voice Channel Leaderboard",
            description="\n".join(lines),
            color=discord.Color.blurple(),
            timestamp=now,
        )
        embed.set_footer(text="🟢 = currently in a voice channel")
        await ctx.send(embed=embed)

    @commands.command(name="saveleaderboard", aliases=["savelb", "slb", "save"])
    @commands.has_permissions(administrator=True)
    async def save_leaderboard(self, ctx):
        checkpoint_all()
        await ctx.send("Saglabāts!")


    @commands.command(name="mytime", aliases=["vc", "vctime"])
    async def my_time(self, ctx):
        """Check your own total voice time. Usage: !mytime"""
        now     = datetime.now(timezone.utc)
        uid     = ctx.author.id
        total   = voice_totals.get(uid, 0)
        if uid in voice_sessions:
            total += (now - voice_sessions[uid]).total_seconds()

        best    = voice_bests.get(uid, 0)

        if total == 0:
            await ctx.send(f"⏱️ {ctx.author.mention} You haven't spent any time in voice yet!")
            return

        embed = discord.Embed(
            title=f"⏱️ {ctx.author.display_name}'s Voice Stats",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Total Time",    value=format_duration(total), inline=True)
        embed.add_field(name="Personal Best", value=format_duration(best),  inline=True)
        await ctx.send(embed=embed)


    
    # ── Personal Stats ────────────────────────────────────────────────────────────

    @commands.command(name="pb")
    async def personal_best(self, ctx, member: discord.Member = None):
        """Show personal best single session. Usage: !pb [@user]"""
        target = member or ctx.author
        best   = voice_bests.get(target.id, 0)

        if best == 0:
            await ctx.send(f"📭 {target.display_name} has no recorded sessions yet.")
        else:
            await ctx.send(f"🏅 **{target.display_name}'s** longest single session: **{format_duration(best)}**")


    @commands.command(name="pbleaderboard", aliases=["pblb"])
    async def pb_leaderboard(self, ctx, top: int = 10):
        """Show personal best leaderboard. Usage: !pblb [top N]"""
        if not voice_bests:
            await ctx.send("📭 No personal bests recorded yet.")
            return

        sorted_bests = sorted(voice_bests.items(), key=lambda x: x[1], reverse=True)[:top]
        medals = ["🥇", "🥈", "🥉"]
        lines  = []
        for i, (uid, secs) in enumerate(sorted_bests):
            m    = ctx.guild.get_member(uid)
            name = m.display_name if m else f"Unknown ({uid})"
            medal = medals[i] if i < 3 else f"`{i + 1}.`"
            lines.append(f"{medal} **{name}** — {format_duration(secs)}")

        embed = discord.Embed(
            title="🏅 Personal Best Leaderboard",
            description="\n".join(lines),
            color=discord.Color.green(),
        )
        embed.set_footer(text="Longest single voice session per person")
        await ctx.send(embed=embed)


    # ------ events
    @commands.Cog.listener("on_voice_state_update")
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
    
        # update streak
        _update_streak(member.id)

        now    = datetime.now(timezone.utc)
        joined = before.channel is None and after.channel is not None
        left   = before.channel is not None and after.channel is None

        if joined:
            voice_sessions[member.id] = now

        elif left and member.id in voice_sessions:
            elapsed = (now - voice_sessions.pop(member.id)).total_seconds()
            voice_totals[member.id] = voice_totals.get(member.id, 0) + elapsed

            # Update personal best if this session was their longest
            if elapsed > voice_bests.get(member.id, 0):
                voice_bests[member.id] = elapsed
                save_bests(voice_bests)

            save_totals(voice_totals)
    
    @commands.Cog.listener("on_ready")
    async def on_ready(self):
        now = datetime.now(timezone.utc)
        already_in_vc = 0
        for guild in self.bot.guilds:
            for vc in guild.voice_channels:
                for member in vc.members:
                    if not member.bot:
                        voice_sessions[member.id] = now
                        already_in_vc += 1
                        # streak
                        _update_streak(member.id)
        print(f"📡 Found {already_in_vc} member(s) already in voice channels")
        print(f"💾 Loaded totals for {len(voice_totals)} member(s)")

async def setup(bot):
    await bot.add_cog(Voice(bot))