import aiohttp
import asyncio
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

async def test_solscan_token():
    # The token address we want to look up from your output
    token_address = "BYVZqFsNf5Pygq2jxwpAzxHJfiPDZ5m8nNjKiJQQgPsF"

    # Try the public API endpoint instead
    url = f"https://public-api.solscan.io/token/meta?token={token_address}"
    headers = {
        "accept": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Authorization": f"Bearer {os.getenv('SOLSCAN_API_KEY')}",
        "Origin": "https://solscan.io",
        "Referer": "https://solscan.io/"
    }

    print(f"Attempting to fetch metadata for token: {token_address}")
    print(f"URL: {url}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                print(f"Response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    print("\nRaw Solscan response:", data)

                    # Let's see what the output would look like in our format
                    token_info = {
                        "symbol": data.get("data", {}).get("symbol", "Unknown"),
                        "decimals": data.get("data", {}).get("decimals", 9),
                    }
                    print("\nFormatted for our use:", token_info)

                    # Show how the swap message would look
                    print("\nSwap message would be:")
                    print(
                        f"swapped on Raydium 0.008 SOL to 22,159.778 {token_info['symbol']}"
                    )
                else:
                    response_text = await response.text()
                    print(f"Error response: {response_text}")
                    
                    # Let's try Jupiter API as a fallback
                    print("\nTrying Jupiter API as a fallback...")
                    jupiter_url = "https://token.jup.ag/all"
                    async with session.get(jupiter_url) as jupiter_response:
                        if jupiter_response.status == 200:
                            tokens = await jupiter_response.json()
                            token_info = next(
                                (token for token in tokens if token["address"] == token_address),
                                None
                            )
                            if token_info:
                                print("Found token info from Jupiter:", token_info)
                            else:
                                print("Token not found in Jupiter API")
                    
    except Exception as e:
        print(f"Error fetching token info: {e}")


# Run the test
if __name__ == "__main__":
    print("Starting Solscan API test...")
    asyncio.run(test_solscan_token())
