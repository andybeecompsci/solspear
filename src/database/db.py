# import libraries needed
from motor.motor_asyncio import AsyncIOMotorClient  # mongodb async driver
import os 
from dotenv import load_dotenv # loading .env file

# load .env
load_dotenv()

# create db class
class Database:
    def __init__(self):
        self.client = None # our connection to the database
        self.db = None # our db

    # connect to db method
    async def connect(self):
        """connect to mongodb"""
        try:
            self.client = AsyncIOMotorClient(os.getenv('MONGODB_URI')) # connect using .env
            self.db = self.client.solspear # get reference to 'solspear' db
            print('connected to mongodb')

            # set up collections (like tables in sql hehe)
            await self.create_collections()
        except Exception as e:
            print(f"error connecting to mongodb: {e}")
            raise e

    async def create_collections(self):
        """create necessary collections with validators"""
        # user collection - stores discord user info
        if "users" not in await self.db.list_collection_names():
            await self.db.create_collection("users")
            # create index on discord_id for faster lookups
            await self.db.users.create_index("discord_id", unique=True) # unique=true to ensure only 1 discord id per user

        # tracked wallets collection - stores wallet address being monitored
        if "tracked_wallets" not in await self.db.list_collection_names():
            await self.db.create_collection("tracked_wallets")
            # create compound index for user_id and wallet_address
            await self.db.tracked_wallets.create_index([
                ("user_id", 1), # 1 = ascending order
                ("wallet_address", 1)
            ], unique=True)

        # transaction history collection - stores transaction history for a wallet
        if "transactions" not in await self.db.list_collection_names():
            await self.db.create_collection("transactions")
            # create index for faster transaction lookups
            await self.db.transactions.create_index([
                ("wallet_address", 1),
                ("timestamp", -1) # -1 = descending order
            ])

    async def close(self):
        """close the connection to mongodb"""
        if self.client:
            self.client.close()
            print("disconnected from mongodb")

# create single instance of our db
db = Database()
