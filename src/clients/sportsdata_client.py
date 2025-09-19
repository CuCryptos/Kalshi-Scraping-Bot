# src/clients/sportsdata_client.py

import requests
import asyncio
from asyncio import Queue
from datetime import datetime
from src.utils.logging_setup import get_trading_logger

# IMPORTANT: Make sure your API Key is correct
SPORTSDATA_API_KEY = "YOUR_SPORTSDATA_API_KEY_HERE"

class SportsDataClient:
    """
    Connects to the SportsData.io API for real-time event data via polling.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.sportsdata.io/v3"
        self.logger = get_trading_logger("sportsdata_client")

    def get_live_games_for_sport(self, sport: str = 'mlb') -> list:
        """
        Fetches all games for the current date and filters for those in-progress.
        """
        # --- DYNAMIC DATE LOGIC ---
        # This now uses the current date every time it's called.
        current_date_str = datetime.now().strftime('%Y-%m-%d')
        
        url = f"{self.base_url}/{sport}/scores/json/GamesByDate/{current_date_str}"
        try:
            response = requests.get(url, params={"key": self.api_key})
            response.raise_for_status()
            all_games = response.json()
            
            # Filter for games that have started but not finished
            live_games = [
                game for game in all_games 
                if game.get("Status") == "InProgress"
            ]
            return live_games
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching live games: {e}")
            return []

    async def poll_for_updates(self, data_queue: Queue, sport: str = 'mlb'):
        """
        Polls the API at a high frequency to simulate a real-time stream.
        """
        self.logger.info(f"✅ Starting high-frequency polling for '{sport}'")
        while True:
            live_games = self.get_live_games_for_sport(sport)
            if live_games:
                # Put the list of all live games onto the queue
                await data_queue.put({"type": "update", "games": live_games})
            
            # Poll every few seconds. Be mindful of your API plan's rate limits.
            await asyncio.sleep(10) # Using a slightly safer 10-second poll
