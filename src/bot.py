import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv
from database.db import db  # import our database connection
from base58 import b58decode  # for validating solana addresses
from discord.ext import tasks  # for creating background tasks
from solana.rpc.api import Client  # solana blockchain api client
from solders.pubkey import Pubkey  # for converting wallet address strings to Pubkey objects
import asyncio
from datetime import datetime, timezone

# load environment variables from .env file
load_dotenv()

class SolSpearBot(commands.Bot):
    def __init__(self):
        # set up all intents we need
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True  # needed for guild/server related commands
        super().__init__(command_prefix='!', intents=intents)
        
        # initialize solana client for blockchain interactions
        self.solana = Client("https://api.mainnet-beta.solana.com")

    async def setup_hook(self):
        # connect to database before bot starts
        print('connecting to database...')
        await db.connect()
        print('connected to database!')
        
        # force sync slash commands globally
        print('syncing commands globally...')
        try:
            await self.tree.sync()
            print(f'synced {len(self.tree.get_commands())} commands!')
            print('available commands:')
            for cmd in self.tree.get_commands():
                print(f'- /{cmd.name}: {cmd.description}')
        except Exception as e:
            print(f'failed to sync commands: {e}')

        # start transaction monitoring
        self.check_transactions.start()

    @tasks.loop(seconds=10) #check for new transactions every 10 seconds
    async def check_transactions(self):
        try:
            # get all wallets we're currently tracking
            tracked_wallets = await db.db.tracked_wallets.find({}).to_list(length=None)

            for wallet in tracked_wallets:
                # fetch recent transactions for this wallet from solana
                wallet_pubkey = Pubkey.from_string(wallet['wallet_address'])
                response = self.solana.get_signatures_for_address(wallet_pubkey)
                
                # solders package returns transactions directly in response.value
                if response and hasattr(response, 'value'):
                    transactions = response.value
                    
                    # find most recent transaction we have processed
                    last_sig = await db.db.transactions.find_one(
                        {"wallet_address": wallet['wallet_address']},
                        sort=[("timestamp", -1)]
                    )

                    # if this is the first time checking this wallet, only store the most recent transaction
                    if not last_sig and transactions:
                        tx = transactions[0]  # get most recent transaction
                        tx_data = {
                            "wallet_address": wallet['wallet_address'],
                            "signature": str(tx.signature),
                            "timestamp": datetime.now(timezone.utc),
                            "slot": tx.slot,
                            "err": tx.err is not None,
                            "memo": None,
                            "processed": False
                        }
                        await db.db.transactions.insert_one(tx_data)
                        continue  # skip to next wallet
                    
                    # look through new transactions
                    for tx in transactions:
                        # skip if we have already processed this transaction
                        if last_sig and tx.signature == last_sig['signature']:
                            break
                        
                        # prepare transaction data for storage
                        tx_data = {
                            "wallet_address": wallet['wallet_address'],
                            "signature": str(tx.signature),
                            "timestamp": datetime.now(timezone.utc),
                            "slot": tx.slot,
                            "err": tx.err is not None,
                            "memo": None,
                            "processed": False
                        }
                        
                        # save transaction to db
                        await db.db.transactions.insert_one(tx_data)
                        
                        # send notification to the wallet's private channel
                        channel = self.get_channel(int(wallet['channel_id']))
                        if channel:
                            await channel.send(
                                f"🔔 New transaction detected!\n"
                                f"Signature: `{tx_data['signature']}`\n"
                                f"Status: {'✅ Success' if not tx_data['err'] else '❌ Failed'}\n"
                                f"View transaction: https://solscan.io/tx/{tx_data['signature']}"
                            )
                            
        except Exception as e:
            print(f"error in transaction monitoring: {e}")
    
    @check_transactions.before_loop
    async def before_check_transactions(self):
        #wait for bot to be ready before monitoring starts
        await self.wait_until_ready()

    async def close(self):
        # cleanup when bot shuts down
        await db.close()
        await super().close()


#create bot instance
bot = SolSpearBot()

#event that triggers when bot is ready
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    # force sync commands for each guild
    for guild in bot.guilds:
        try:
            await bot.tree.sync(guild=guild)
            print(f'synced commands for guild: {guild.name}')
        except Exception as e:
            print(f'failed to sync commands for guild {guild.name}: {e}')


#slash command to create a private channel for the user
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


#db test to see if user gets put in db if user is not in db
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


#track wallet command yippee
@bot.tree.command(name='track', description='track a solana wallet')
async def track_wallet(interaction: discord.Interaction, wallet_address: str):
    try:
        # validate solana wallet address( should be base 58 and 32 bytes)
        try:
            decoded = b58decode(wallet_address)
            if len(decoded) != 32:
                raise ValueError("Invalid wallet address length")
        except Exception:
            await interaction.response.send_message(
                "that doesnt look like a solana wallet address, please check and try again",
                ephemeral=True
            )
            return

        # check if wallet is already being tracked by this user
        existing_wallet = await db.db.tracked_wallets.find_one({
            "user_id": str(interaction.user.id),
            "wallet_address": wallet_address
        })

        # if wallet exists and has a channel, it's actively being tracked
        if existing_wallet and 'channel_id' in existing_wallet:
            try:
                channel = interaction.guild.get_channel(int(existing_wallet['channel_id']))
                if channel:
                    await interaction.response.send_message(
                        f"you're already tracking this wallet in {channel.mention}",
                        ephemeral=True
                    )
                    return
            except:
                # channel doesn't exist anymore, we'll recreate it
                pass

        # create private channel
        channel_name = f"wallet-{wallet_address[:4]}-{wallet_address[-4:]}" #shows first and last 4 digits of wallet address
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True),
            interaction.user: discord.PermissionOverwrite(read_messages=True),
        } 

        channel = await interaction.guild.create_text_channel(
            name = channel_name,
            overwrites = overwrites,
            reason=f"wallet tracking channel for {wallet_address}"
        )

        # if wallet exists but has no channel (was deleted), update it
        if existing_wallet:
            await db.db.tracked_wallets.update_one(
                {"_id": existing_wallet["_id"]},
                {
                    "$set": {
                        "channel_id": str(channel.id),
                        "created_at": discord.utils.utcnow().isoformat()
                    }
                }
            )
        else:
            # create new wallet tracking entry
            await db.db.tracked_wallets.insert_one({
                "user_id": str(interaction.user.id),
                "wallet_address": wallet_address,
                "channel_id": str(channel.id),
                "created_at": discord.utils.utcnow().isoformat(),
                "threshold": [] #for future threshold alerts, come back to this later
            })

        # send success message
        await interaction.response.send_message(
            f"now tracking wallet {wallet_address}! check {channel.mention} for updates",
            ephemeral=True
        )

    except Exception as e:
        print(f"error tracking wallet: {e}")
        await interaction.response.send_message(
            "oops something went wrong while setting up your wallet, please try again later",
            ephemeral=True
        )
        # if channel was created but db operations failed, delete the channel
        try:
            if 'channel' in locals():
                await channel.delete()
        except:
            pass


# add this after your other event handlers

@bot.event
async def on_guild_channel_delete(channel):
    try:
        # check if this was a wallet tracking channel
        if channel.name.startswith('wallet-'):
            # find and delete the wallet from database
            result = await db.db.tracked_wallets.delete_one({"channel_id": str(channel.id)})
            if result.deleted_count > 0:
                print(f"removed wallet tracking for deleted channel: {channel.name}")
            
    except Exception as e:
        print(f"error cleaning up deleted channel: {e}")


#run bot with token
TOKEN = os.getenv('DISCORD_TOKEN')
bot.run(TOKEN)
