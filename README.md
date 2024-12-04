# SolSpear: Solana Whale Tracking Discord Bot

## Overview
SolSpear is a Discord bot designed to track significant wallet activities on the Solana blockchain. The bot provides users with real-time notifications, wallet analytics, and insights into whale transactions.

## Features
- Real-time wallet tracking
- Threshold-based alerts
- Token swap monitoring
- Fiat value conversion
- Private channel management

## Installation

### Prerequisites
- Python 3.9+
- MongoDB
- Discord Bot Token
- Solana API access

### Setup
1. Clone the repository
```bash
git clone [your-repo-url]
cd solspear
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Create and configure `.env` file
```bash
DISCORD_TOKEN=your_bot_token
MONGODB_URI=your_mongodb_uri
```

4. Run the bot
```bash
python src/bot.py
```

## Usage
- `/private` - Creates a private channel for wallet tracking
- `/track <wallet>` - Start tracking a Solana wallet
- `/threshold <token> <amount>` - Set transaction threshold alerts

## Development
Currently in active development. See project documentation for planned features and roadmap.

## License
[Your chosen license]

## Contributing
[Your contribution guidelines] 