import discord
from discord.ext import commands
import os

WORDS_FILE = "words.txt" 
DEFAULT_BANNED = [
    "i like jews"
]
SCOLDS = [
    "Aizej nošaujies. Nelegāls vārds. {mention}",
]


def load_banned() -> list:
    """Load banned words from words.txt — one word/phrase per line."""
    if os.path.exists(WORDS_FILE):
        with open(WORDS_FILE, "r") as f:
            return [line.strip().lower() for line in f if line.strip()]
    # Create the file with defaults if it doesn't exist
    save_banned(DEFAULT_BANNED)
    return list(DEFAULT_BANNED)

def save_banned(words: list) -> None:
    """Write banned words back to words.txt."""
    with open(WORDS_FILE, "w") as f:
        f.write("\n".join(words))


# ------ state

banned_words: list[str] = load_banned()


class Words(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        """Scan every message for banned words/phrases from words.txt and scold if found."""
        if message.author.bot:
            return

        content_lower = message.content.lower()
        triggered = [w for w in banned_words if w in content_lower]

        if triggered:
            import random
            scold = random.choice(SCOLDS).format(mention=message.author.mention)
            await message.channel.send(scold)
            # message is kept — just scolded publicly

        
    @commands.command(name="addword")
    @commands.has_permissions(administrator=True)
    async def add_word(self, ctx, *, phrase: str):
        """Add a banned phrase to words.txt. Usage: !addword <phrase>"""
        phrase = phrase.lower().strip()
        if phrase in banned_words:
            await ctx.send(f"⚠️ `{phrase}` is already banned.")
            return
        banned_words.append(phrase)
        save_banned(banned_words)
        await ctx.send(f"🚫 `{phrase}` added to words.txt.")

    @commands.command(name="removeword")
    @commands.has_permissions(administrator=True)
    async def remove_word(self, ctx, *, phrase: str):
        """Remove a banned phrase from words.txt. Usage: !removeword <phrase>"""
        phrase = phrase.lower().strip()
        if phrase not in banned_words:
            await ctx.send(f"⚠️ `{phrase}` isn't on the banned list.")
            return
        banned_words.remove(phrase)
        save_banned(banned_words)
        await ctx.send(f"✅ `{phrase}` removed from words.txt.")

    @commands.command(name="bannedwords", aliases=["wordlist"])
    @commands.has_permissions(administrator=True)
    async def list_banned(self, ctx):
        """List all banned words/phrases. Usage: !bannedwords"""
        if not banned_words:
            await ctx.send("✅ No banned words set.")
            return
        formatted = "\n".join(f"• `{w}`" for w in banned_words)
        embed = discord.Embed(
            title="🚫 Banned Words/Phrases",
            description=formatted,
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)

    @commands.Cog.listener("on_ready")
    async def on_ready(self):
        print(f"🚫 {len(banned_words)} banned word(s) loaded")

async def setup(bot):
    await bot.add_cog(Words(bot))

