import discord
from discord.ext import commands
import os
import contextlib
import io

TRUSTED_USERS = set(
    int(uid.strip())
    for uid in os.getenv("TRUSTED_USERS", "").split(",")
    if uid.strip().isdigit()
)

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ping", aliases=["pong"])
    async def ping(self, ctx):
        await ctx.send(f"🏓 Pong! Latency: `{round(self.bot.latency * 1000)}`ms")

    @commands.command(name="hello", aliases=["Cau"])
    async def hello(self, ctx):
        await ctx.send(f"Cau, {ctx.author.mention}! 👋")

    @commands.command(name="info", aliases=["serverinfo"])
    async def info(self, ctx):
        guild = ctx.guild
        embed = discord.Embed(title=f"📋 {guild.name}", color=discord.Color.blurple())
        embed.add_field(name="Members",  value=guild.member_count,           inline=True)
        embed.add_field(name="Channels", value=len(guild.text_channels),     inline=True)
        embed.add_field(name="Created",  value=guild.created_at.strftime("%b %d, %Y"), inline=True)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        await ctx.send(embed=embed)

    @commands.command(name="exec")
    async def exec_code(self, ctx, *, code: str):
        """Execute Python code. Trusted users only. Usage: !exec <code>"""
        if ctx.author.id not in TRUSTED_USERS:
            await ctx.send("🚫 You're not allowed to use this command.")
            return
    
        code = code.strip()
        if code.startswith("```"):
            code = code.split("\n", 1)[-1]   # drop opening ```python line
            code = code.rsplit("```", 1)[0]  # drop closing ```
        code = code.strip()
    
        # Capture stdout and stderr
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
    
        try:
            with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
                exec(compile(code, "<discord>", "exec"), {"bot": self.bot, "ctx": ctx, "discord": discord})
            output = stdout_buf.getvalue()
            error  = stderr_buf.getvalue()
        except Exception as e:
            output = ""
            error  = f"{type(e).__name__}: {e}"
    
        result = ""
        if output: result += f"**stdout:**\n```\n{output[:1800]}\n```"
        if error:  result += f"**stderr:**\n```\n{error[:1800]}\n```"
        if not result: result = "✅ Executed with no output."
    
        await ctx.send(result)

async def setup(bot):
    await bot.add_cog(General(bot))
