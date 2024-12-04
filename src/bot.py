import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv
from database.db import db  # import our database connection

# load environment variables from .env file
load_dotenv()

class SolSpearBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = False  # we don't need this for slash commands
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        # connect to database before bot starts
        print('connecting to database...')
        await db.connect()
        print('connected to database!')
        
        # sync slash commands
        print('syncing commands...')
        await self.tree.sync()
        print(f'synced {len(self.tree.get_commands())} commands!')

    async def close(self):
        # cleanup when bot shuts down
        await db.close()
        await super().close()

bot = SolSpearBot()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} servers')
    print('Available commands:')
    for cmd in bot.tree.get_commands():
        print(f'- /{cmd.name}: {cmd.description}')

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

@bot.tree.command(name='dbtest', description='test db connection')
async def db_test(interaction: discord.Interaction):
    try:
        #get user info from disc
        user_id = str(interaction.user.id)

        #check if user exists in db
        existing_user = await db.db.users.find_one({"discord_id": user_id})

        if existing_user:
            #user exists, send message
            await interaction.response.send_message(
                "youre already in the db",
                ephemeral=True
            )
        else:
            #add new user with default settings
            new_user = {
                "discord_id": user_id,
                "settings": {
                    "preferred_currency": "USD",
                    "notification_preferences": {
                        "large_transactions": True,
                        "token_swaps": True,
                        "price_alerts": True,
                    }
                }
            }
            #insert user into db
            await db.db.users.insert_one(new_user)

            #send single response
            await interaction.response.send_message(
                "welcome to the club, ive addded you to the db",
                ephemeral=True
            )

    except Exception as e:
        print(f"error adding user to db: {e}")
        await interaction.response.send_message(
            "oops something went wrong, working on it...",
            ephemeral=True
        )

#run bot with token
TOKEN = os.getenv('DISCORD_TOKEN')
bot.run(TOKEN)
