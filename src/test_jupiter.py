import aiohttp
import asyncio
from typing import Optional, Dict
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient

async def get_raydium_token_metadata(token_address: str) -> Optional[Dict]:
    """Get token metadata from Raydium API"""
    url = f"https://api.raydium.io/v2/sdk/token/raydium.mainnet.json"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    tokens = await response.json()
                    # Raydium uses a different structure
                    token_info = next(
                        (token for token in tokens['tokens'] if token["mint"] == token_address),
                        None
                    )
                    if token_info:
                        return {
                            "address": token_address,
                            "symbol": token_info.get("symbol"),
                            "name": token_info.get("name"),
                            "decimals": token_info.get("decimals")
                        }
                return None
    except Exception as e:
        print(f"Error fetching from Raydium: {e}")
        return None

async def get_dexscreener_token_metadata(token_address: str) -> Optional[Dict]:
    """Get token metadata from DexScreener API"""
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('pairs') and len(data['pairs']) > 0:
                        token_info = data['pairs'][0]  # Get first trading pair
                        base_token = token_info.get('baseToken', {})
                        quote_token = token_info.get('quoteToken', {})
                        
                        # Check which token matches our address
                        token_data = base_token if base_token.get('address') == token_address else quote_token
                        
                        return {
                            "address": token_address,
                            "symbol": token_data.get("symbol", "Unknown"),
                            "name": token_data.get("name", "Unknown Token"),
                            "decimals": int(token_data.get("decimals", 9))
                        }
                return None
    except Exception as e:
        print(f"Error fetching from DexScreener: {e}")
        return None

async def get_token_metadata(token_address: str) -> Optional[Dict]:
    """
    Get token metadata from multiple sources
    """
    # Try Jupiter first
    url = "https://token.jup.ag/all"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    tokens = await response.json()
                    token_info = next(
                        (token for token in tokens if token["address"] == token_address),
                        None
                    )
                    if token_info:
                        return token_info
                    
                    # If not found in Jupiter, try Raydium
                    print("Token not found in Jupiter, trying Raydium...")
                    raydium_info = await get_raydium_token_metadata(token_address)
                    if raydium_info:
                        return raydium_info
                    
                    # If not found in Raydium, try DexScreener
                    print("Token not found in Raydium, trying DexScreener...")
                    dexscreener_info = await get_dexscreener_token_metadata(token_address)
                    if dexscreener_info:
                        return dexscreener_info
                    
                    print("Token not found in any source")
                    return None
    except Exception as e:
        print(f"Error fetching token info: {e}")
        return None

async def test_jupiter_api():
    # Test with some known tokens
    test_tokens = [
        # USDC
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        # Your memecoin token
        "BYVZqFsNf5Pygq2jxwpAzxHJfiPDZ5m8nNjKiJQQgPsF",
        # SOL (Wrapped SOL)
        "So11111111111111111111111111111111111111112"
    ]
    
    for address in test_tokens:
        print(f"\nFetching metadata for token: {address}")
        token_info = await get_token_metadata(address)
        
        if token_info:
            # Format a clean output
            print(f"✅ Found token:")
            print(f"  Symbol: {token_info.get('symbol', 'Unknown')}")
            print(f"  Name: {token_info.get('name', 'Unknown')}")
            print(f"  Decimals: {token_info.get('decimals', 0)}")
            
            # Example swap message
            amount = 1000000  # 1 USDC for example
            formatted_amount = amount / (10 ** token_info['decimals'])
            print(f"\nExample swap message:")
            print(f"swapped on Raydium 0.008 SOL to {formatted_amount:,.3f} {token_info['symbol']}")
        else:
            print(f"❌ Token not found")

if __name__ == "__main__":
    print("Starting Jupiter API test...")
    asyncio.run(test_jupiter_api()) 