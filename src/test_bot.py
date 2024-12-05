import asyncio
import json
import websockets
import logging
from datetime import datetime
import re
from base58 import b58encode, b58decode
import aiohttp
from typing import Optional, Dict

# set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def get_token_metadata(token_address: str) -> Optional[Dict]:
    """Get token metadata from DexScreener API"""
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('pairs') and len(data['pairs']) > 0:
                        token_info = data['pairs'][0]
                        base_token = token_info.get('baseToken', {})
                        quote_token = token_info.get('quoteToken', {})
                        
                        token_data = base_token if base_token.get('address').lower() == token_address.lower() else quote_token
                        
                        return {
                            "address": token_address,
                            "symbol": token_data.get("symbol", "Unknown"),
                            "name": token_data.get("name", "Unknown Token"),
                            "decimals": int(token_data.get("decimals", 9))
                        }
                return None
    except Exception as e:
        logging.error(f"Error fetching token info: {e}")
        return None

class WalletMonitor:
    def __init__(self):
        self.ws_url = "wss://api.mainnet-beta.solana.com"
        # only hardcoded value - our test wallet
        self.wallet = "Ei4NiwbXE1FdjpZbtBoHk83CoLSGBdspRNtGHb1vhcgo"
        # cache token metadata to avoid repeated RPC calls
        self.token_metadata_cache = {}
        self.reconnect_delay = 5  # initial reconnect delay in seconds
        self.max_reconnect_delay = 60  # maximum reconnect delay
        # Add Jupiter API endpoint
        self.jupiter_api = "https://token.jup.ag/all"
        # Add Solscan API endpoint
        self.solscan_api = "https://public-api.solscan.io/token/meta"
        
    async def initialize(self):
        """Initialize the wallet monitor by fetching token list"""
        await self.fetch_token_list()
        
    async def fetch_token_list(self):
        """Fetch token list from Jupiter or Solana token list"""
        try:
            async with aiohttp.ClientSession() as session:
                # Using Jupiter API for token list
                async with session.get('https://token.jup.ag/all') as response:
                    tokens = await response.json()
                    # Create a mapping of mint address to token info
                    for token in tokens:
                        self.token_metadata_cache[token['address']] = {
                            "symbol": token['symbol'],
                            "decimals": token['decimals']
                        }
                    logging.info(f"Cached {len(tokens)} token metadata entries")
        except Exception as e:
            logging.error(f"Error fetching token list: {e}")

    async def subscribe_to_wallet(self, websocket):
        """Subscribe to account updates and transactions"""
        # Subscribe to account updates
        account_sub = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "accountSubscribe",
            "params": [
                self.wallet,
                {"encoding": "jsonParsed", "commitment": "confirmed"}
            ]
        }
        await websocket.send(json.dumps(account_sub))
        logging.info(f"subscribed to account updates for {self.wallet}")
        
        # Subscribe to transactions
        tx_sub = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "logsSubscribe",
            "params": [
                {"mentions": [self.wallet]},
                {"commitment": "confirmed"}
            ]
        }
        await websocket.send(json.dumps(tx_sub))
        logging.info("subscribed to transaction logs")

    def is_valid_pubkey(self, address):
        """Check if a string is a valid Solana public key"""
        try:
            # valid base58 and 32 bytes length
            decoded = b58decode(address)
            return len(decoded) == 32
        except:
            return False

    async def get_token_metadata(self, mint_address: str) -> Dict[str, any]:
        """Get token metadata using multiple sources"""
        # Check cache first
        if mint_address in self.token_metadata_cache:
            return self.token_metadata_cache[mint_address]

        # Handle wrapped SOL
        if mint_address == "So11111111111111111111111111111111111111112":
            metadata = {"symbol": "SOL", "decimals": 9}
            self.token_metadata_cache[mint_address] = metadata
            return metadata

        # Try different sources to get token metadata
        metadata = await self._try_multiple_sources(mint_address)
        if metadata:
            self.token_metadata_cache[mint_address] = metadata
            return metadata

        return {"symbol": "Unknown", "decimals": 9}

    async def _try_multiple_sources(self, mint_address: str) -> Optional[Dict]:
        """Try multiple sources to get token metadata"""
        try:
            # Try Jupiter API first
            async with aiohttp.ClientSession() as session:
                # Try Jupiter token list
                async with session.get(f"{self.jupiter_api}") as response:
                    if response.status == 200:
                        tokens = await response.json()
                        for token in tokens:
                            if token.get('address') == mint_address:
                                return {
                                    "symbol": token.get('symbol', 'Unknown'),
                                    "decimals": token.get('decimals', 9)
                                }

                # If Jupiter fails, try Solscan
                headers = {'accept': 'application/json'}
                async with session.get(
                    f"{self.solscan_api}/{mint_address}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success', False):
                            return {
                                "symbol": data.get('symbol', 'Unknown'),
                                "decimals": data.get('decimals', 9)
                            }

                # If both fail, try on-chain metadata as last resort
                return await self._get_onchain_metadata(mint_address)

        except Exception as e:
            logging.error(f"Error fetching token metadata from APIs: {e}")
            return None

    async def _get_onchain_metadata(self, mint_address: str) -> Optional[Dict]:
        """Get token metadata from on-chain data"""
        try:
            token_info_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [
                    mint_address,
                    {"encoding": "jsonParsed"}
                ]
            }
            
            async with websockets.connect(self.ws_url) as ws:
                await ws.send(json.dumps(token_info_request))
                response = await ws.recv()
                data = json.loads(response)
                
                if ('result' in data and 
                    data['result'] and 
                    'value' in data['result'] and 
                    'data' in data['result']['value'] and 
                    'parsed' in data['result']['value']['data']):
                    
                    token_data = data['result']['value']['data']['parsed']
                    return {
                        "symbol": token_data['info'].get('symbol', 'Unknown'),
                        "decimals": token_data['info'].get('decimals', 9)
                    }
                
        except Exception as e:
            logging.error(f"Error fetching on-chain metadata: {e}")
            return None

        return None

    def extract_token_addresses(self, logs):
        """Extract token mint addresses from transaction logs"""
        token_addresses = set()
        
        # First look for direct token mentions
        for i, log in enumerate(logs):
            # Check for wrapped SOL
            if "So11111111111111111111111111111111111111112" in log:
                logging.info("Found SOL token address")
                token_addresses.add("So11111111111111111111111111111111111111112")
            
            # Look for specific program logs that contain token addresses
            if "Program log:" in log:
                # Split the log line and look for potential addresses
                parts = log.split("Program log:")
                if len(parts) > 1:
                    content = parts[1].strip()
                    # Look for addresses in the content
                    words = content.split()
                    for word in words:
                        if len(word) == 44 and self.is_valid_pubkey(word):
                            logging.info(f"Found potential token: {word}")
                            token_addresses.add(word)
            
            # Also check for token program invocations
            if "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke" in log:
                # Look at surrounding logs for token addresses
                start_idx = max(0, i - 3)
                end_idx = min(len(logs), i + 3)
                for j in range(start_idx, end_idx):
                    if j < len(logs):
                        words = logs[j].split()
                        for word in words:
                            if len(word) == 44 and self.is_valid_pubkey(word):
                                logging.info(f"Found potential token near token program: {word}")
                                token_addresses.add(word)
        
        # Filter out known non-token addresses
        non_token_programs = {
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # Token program
            "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",  # Associated token program
            "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium program
            "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"   # Jupiter program
        }
        
        token_addresses = {addr for addr in token_addresses if addr not in non_token_programs}
        
        logging.info(f"All found token addresses: {token_addresses}")
        return list(token_addresses)

    def parse_swap_amounts(self, swap_info):
        """Parse swap amounts with proper decimal handling"""
        try:
            amount_in = float(swap_info.get('amount_in', 0))
            amount_out = float(swap_info.get('amount_out', 0))
            return amount_in, amount_out
        except (ValueError, TypeError) as e:
            logging.error(f"Error parsing swap amounts: {e}")
            return 0, 0

    async def parse_swap_details(self, logs):
        """Parse swap details from transaction logs"""
        try:
            # First check for Raydium SwapEvent
            for i, log in enumerate(logs):
                if "SwapEvent" in log:
                    logging.info(f"Found SwapEvent log: {log}")
                    # Parse amounts from SwapEvent
                    parts = log.split("SwapEvent {")[1].split("}")
                    details = parts[0].split(",")
                    swap_info = {}
                    for detail in details:
                        if ":" in detail:
                            key, value = detail.split(":")
                            swap_info[key.strip()] = value.strip()
                    
                    logging.info(f"Parsed swap info: {swap_info}")
                    
                    # Get token addresses from logs before SwapEvent
                    token_logs = logs[max(0, i-20):i]
                    token_addresses = self.extract_token_addresses(token_logs)
                    
                    if len(token_addresses) >= 2:
                        logging.info("Found at least 2 token addresses")
                        # Get metadata for both tokens using DexScreener
                        token_in_meta = await get_token_metadata(token_addresses[0])
                        token_out_meta = await get_token_metadata(token_addresses[1])
                        
                        if token_in_meta and token_out_meta:
                            logging.info(f"Token metadata - In: {token_in_meta}, Out: {token_out_meta}")
                            
                            # Parse amounts using proper decimals
                            amount_in, amount_out = self.parse_swap_amounts(swap_info)
                            amount_in = amount_in / (10 ** token_in_meta['decimals'])
                            amount_out = amount_out / (10 ** token_out_meta['decimals'])
                            
                            return {
                                "dex": "Raydium",
                                "token_in": token_in_meta['symbol'],
                                "token_out": token_out_meta['symbol'],
                                "amount_in": amount_in,
                                "amount_out": amount_out
                            }

            # Check for Jupiter swap
            if "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4" in str(logs):
                logging.info("Found Jupiter swap")
                token_addresses = self.extract_token_addresses(logs)
                
                if len(token_addresses) >= 2:
                    token_in_meta = await get_token_metadata(token_addresses[0])
                    token_out_meta = await get_token_metadata(token_addresses[1])
                    
                    if token_in_meta and token_out_meta:
                        logging.info(f"Jupiter - Token metadata - In: {token_in_meta}, Out: {token_out_meta}")
                        
                        # Try to find amounts in logs
                        amount_in = 0
                        amount_out = 0
                        for log in logs:
                            if "amount_in:" in log:
                                amount_in = float(log.split("amount_in:")[1].split(",")[0].strip())
                            if "amount_out:" in log:
                                amount_out = float(log.split("amount_out:")[1].split(",")[0].strip())
                        
                        return {
                            "dex": "Jupiter",
                            "token_in": token_in_meta['symbol'],
                            "token_out": token_out_meta['symbol'],
                            "amount_in": amount_in / (10 ** token_in_meta['decimals']),
                            "amount_out": amount_out / (10 ** token_out_meta['decimals'])
                        }

            return None

        except Exception as e:
            logging.error(f"Error parsing swap details: {e}")
            return None

    async def handle_messages(self, websocket):
        """Process incoming websocket messages"""
        try:
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    # log raw data for debugging
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    logging.info(f"[{timestamp}] received update: {data}")

                    # handle transaction logs
                    if data.get('method') == 'logsNotification':
                        logs = data.get('params', {}).get('result', {}).get('value', {}).get('logs', [])
                        
                        # try to parse swap
                        swap = await self.parse_swap_details(logs)
                        if swap:
                            print(f"swapped on {swap['dex']} {swap['amount_in']:.3f} {swap['token_in']} to {swap['amount_out']:,.3f} {swap['token_out']}")

                    # we don't need account notifications anymore
                    elif data.get('method') == 'accountNotification':
                        pass

                except websockets.exceptions.ConnectionClosed:
                    logging.warning("WebSocket connection closed, attempting to reconnect...")
                    raise  # propagate to outer try/except for reconnection
                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding message: {e}")
                    continue
                except Exception as e:
                    logging.error(f"Error processing message: {e}")
                    continue

        except Exception as e:
            logging.error(f"WebSocket error: {e}")
            raise  # propagate to monitor_wallet for reconnection

    async def monitor_wallet(self):
        """Main monitoring loop with reconnection logic"""
        current_delay = self.reconnect_delay
        
        while True:
            try:
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=30,  # send ping every 30 seconds
                    ping_timeout=10,   # wait 10 seconds for pong response
                    close_timeout=10   # wait 10 seconds for close frame
                ) as websocket:
                    logging.info("connected to solana websocket")
                    await self.subscribe_to_wallet(websocket)
                    current_delay = self.reconnect_delay  # reset delay on successful connection
                    await self.handle_messages(websocket)
                    
            except (websockets.exceptions.ConnectionClosed,
                    websockets.exceptions.InvalidStatusCode,
                    websockets.exceptions.InvalidMessage,
                    ConnectionRefusedError) as e:
                logging.error(f"connection error: {e}")
                
            except Exception as e:
                logging.error(f"unexpected error: {e}")
                
            finally:
                # Exponential backoff for reconnection attempts
                logging.info(f"attempting to reconnect in {current_delay} seconds...")
                await asyncio.sleep(current_delay)
                current_delay = min(current_delay * 2, self.max_reconnect_delay)

async def main():
    while True:  # Keep trying to run the monitor even if it fails
        try:
            monitor = WalletMonitor()
            await monitor.initialize()
            await monitor.monitor_wallet()
        except Exception as e:
            logging.error(f"Fatal error in main loop: {e}")
            await asyncio.sleep(5)  # Wait before restarting the entire monitor

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("shutting down wallet monitor...")
