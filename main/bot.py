import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class SolSpearBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f'Synced slash commands for {self.user}')


bot = SolSpearBot()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.tree.command(name='private', description='Creates a private channel for you')
async def create_private_channel(interaction: discord.Interaction):
    #get the guild (server) and member who triggered the command
    guild = interaction.guild
    member = interaction.user

    #create channel permissions
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        member: discord.PermissionOverwrite(read_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True),
    }

    #create the channel
    channel_name = f"private-{member.name}"
    try:
        channel = await guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            reason=f"Private channel for {member.name}"
        )
        #send a message to the user
        await interaction.response.send_message(
            f"Created your private channel {channel.mention}",
            ephemeral=True #only the user can see the message
        )
        #handles error where the bot doesn't have permission to create channels
    except discord.Forbidden:
        await interaction.response.send_message(
            "I don't have permission to create channels!",
            ephemeral=True
        )

#run bot with token
TOKEN = os.getenv('DISCORD_TOKEN')
bot.run(TOKEN)
