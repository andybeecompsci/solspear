import aiohttp
import asyncio
from typing import Optional, Dict

async def get_token_metadata(token_address: str) -> Optional[Dict]:
    """
    Get token metadata from DexScreener API
    
    Args:
        token_address: The token's mint address
        
    Returns:
        Dictionary containing token metadata or None if not found
        Example: {
            "address": "token_address",
            "symbol": "TOKEN",
            "name": "Token Name",
            "decimals": 9
        }
    """
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
                        token_data = base_token if base_token.get('address').lower() == token_address.lower() else quote_token
                        
                        return {
                            "address": token_address,
                            "symbol": token_data.get("symbol", "Unknown"),
                            "name": token_data.get("name", "Unknown Token"),
                            "decimals": int(token_data.get("decimals", 9))
                        }
                    print(f"No trading pairs found for token: {token_address}")
                    return None
                else:
                    print(f"Error: DexScreener API returned status {response.status}")
                    return None
    except Exception as e:
        print(f"Error fetching token info: {e}")
        return None

async def test_dexscreener():
    # Test with some known tokens
    test_tokens = [
        # USDC
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        # Okapi token
        "BYVZqFsNf5Pygq2jxwpAzxHJfiPDZ5m8nNjKiJQQgPsF",
        # SOL (Wrapped SOL)
        "So11111111111111111111111111111111111111112"
    ]
    
    for address in test_tokens:
        print(f"\nFetching metadata for token: {address}")
        token_info = await get_token_metadata(address)
        
        if token_info:
            print(f"✅ Found token:")
            print(f"  Symbol: {token_info['symbol']}")
            print(f"  Name: {token_info['name']}")
            print(f"  Decimals: {token_info['decimals']}")
            
            # Example swap message
            amount = 1000000  # 1 USDC for example
            formatted_amount = amount / (10 ** token_info['decimals'])
            print(f"\nExample swap message:")
            print(f"swapped on Raydium 0.008 SOL to {formatted_amount:,.3f} {token_info['symbol']}")
        else:
            print(f"❌ Token not found")

if __name__ == "__main__":
    print("Starting DexScreener API test...")
    asyncio.run(test_dexscreener()) 