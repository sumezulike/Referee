import discord
from discord.ext import commands

from db_classes.PGModmailDB import PGModmailDB

from models import modmail_models

MOD_CHANNEL_ID = 539570743168466958


class ModMail(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mod_channel: discord.TextChannel = self.bot.get_channel(MOD_CHANNEL_ID)
        self.db = PGModmailDB()

    async def on_message(self, message: discord.Message):
        if isinstance(message.channel, discord.DMChannel):
            await self.process_modmail(message)

    async def process_modmail(self, message: discord.Message):
        mail = modmail_models.ModMail(author_id=message.author.id, author_name=message.author.discriminator, timestamp=message.created_at, content=message.content)
        self.db.put_modmail(mail)
        await self.report(mail)

    async def report(self, mail: modmail_models.ModMail):
        embed = discord.Embed(title=f"New ModMail by {mail.author_name}")
        embed.add_field(name="Content", value=mail.content)
        embed.add_field(name="Answered", value="")


        await self.mod_channel.send()


    @commands.command
    @commands.has_permissions(kick_members=True)
    async def answer(self, ctx: commands.Context, modmail_id: int, *, message: str):
        pass

    @commands.command
    @commands.has_permissions(kick_members=True)
    async def recent(self, ctx: commands.Context, number: int = 5):
        pass


def setup(bot: commands.Bot):
    bot.add_cog(ModMail(bot))
