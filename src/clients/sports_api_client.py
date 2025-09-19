# src/clients/sports_api_client.py

import asyncio
import json
import websockets
from asyncio import Queue
from src.utils.logging_setup import get_trading_logger

# IMPORTANT: Add your API Key here
# It's best practice to load this from your settings/environment variables
ODDS_API_KEY = "dd97853b8b17fb7a42afbca11e0be870"

class SportsAPIClient:
    """
    Connects to The Odds API WebSocket for real-time event data.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_ws_url = "wss://ws.the-odds-api.com"
        self.logger = get_trading_logger("sports_api_client")

    async def listen_for_events(self, trade_queue: Queue, sport: str = 'basketball_nba'):
        """

        Connects to the WebSocket and streams live data into the trade_queue.
        This function will run indefinitely until the connection is lost.
        """
        ws_url = f"{self.base_ws_url}/v4/live/{sport}?apiKey={self.api_key}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                self.logger.info(f"✅ Successfully connected to The Odds API WebSocket for '{sport}'")
                
                # The first message is a connection confirmation
                confirmation = await websocket.recv()
                self.logger.info(f"Connection confirmed: {confirmation}")

                # Listen for incoming messages forever
                async for message in websocket:
                    data = json.loads(message)
                    
                    # The Odds API sends two types of messages: 'update' and 'heartbeat'
                    # We only care about updates containing scores or odds changes.
                    if data.get("type") == "update":
                        self.logger.debug(f"Received event update: {data}")
                        # Put the entire event data onto the queue for the scalping job to parse
                        await trade_queue.put(data)

        except websockets.exceptions.ConnectionClosed as e:
            self.logger.error(f"WebSocket connection closed: {e}")
            # In a production system, you'd add reconnection logic here
            await asyncio.sleep(10)
        except Exception as e:
            self.logger.error(f"An error occurred with the WebSocket connection: {e}")
            await asyncio.sleep(10)


# Example of how you would use this client
async def main():
    # This is just for testing the client directly
    test_queue = Queue()
    client = SportsAPIClient(api_key=ODDS_API_KEY)
    await client.listen_for_events(test_queue)

if __name__ == "__main__":
    asyncio.run(main())
