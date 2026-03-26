import discord
from discord.ext import commands


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="clear", aliases=["purge"])
    @commands.has_permissions(manage_messages=True)
    async def clear(ctx, amount: int = 5):
        if amount < 1 or amount > 100:
            await ctx.send("❌ Iesmēre man ziņu skaitu cik man izdēst no 1 līdz 100.")
            return
        deleted = await ctx.channel.purge(limit=amount + 1)
        confirm = await ctx.send(f"🗑️ Izdzēsu {len(deleted) - 1} ziņu/as.")
        await confirm.delete(delay=3)

    @commands.Cog.listener("on_ready")
    async def on_ready(self):
        print(f"✅ Logged in as {self.bot.user} (ID: {self.bot.user.id})")

async def setup(bot):
    await bot.add_cog(Admin(bot))
