import discord
from discord.ext import commands
import os
TRUSTED_USERS = set(
    int(uid.strip())
    for uid in os.getenv("TRUSTED_USERS", "").split(",")
    if uid.strip().isdigit()
)

pending_movebacks: set[int] = set()


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """
        If a trusted user is deafened, muted then they are unmuted, undeafened
        if the user is moved to a diff channel move them back
        """
        if member.bot:
            return

        # Auto-unmute/undeafen trusted users
        if member.id in TRUSTED_USERS and after.channel is not None:
            if after.mute or after.deaf:
                await member.edit(mute=False, deafen=False)


        moved = (
            before.channel is not None and
            after.channel is not None and
            before.channel != after.channel
        )
        if moved and member.id in TRUSTED_USERS:
            if member.id in pending_movebacks:
                # This is the bot's own move completing — clear the flag and stop
                pending_movebacks.discard(member.id)
            else:
                # Someone else moved them — move them back
                pending_movebacks.add(member.id)
                await member.move_to(before.channel)
 


async def setup(bot):
    await bot.add_cog(Events(bot))
