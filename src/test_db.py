import asyncio
from database.db import db

async def test_connection():
    try:
        # try to connect
        await db.connect()
        
        # list all collections to verify they were created
        collections = await db.db.list_collection_names()
        print(f"collections created: {collections}")
        
        # close the connection
        await db.close()
        
    except Exception as e:
        print(f"test failed: {e}")

# run the test
if __name__ == "__main__":
    asyncio.run(test_connection()) 