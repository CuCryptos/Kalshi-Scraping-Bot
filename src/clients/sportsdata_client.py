# src/clients/sportsdata_client.py

import requests
import asyncio
from asyncio import Queue
from src.utils.logging_setup import get_trading_logger

# IMPORTANT: Add your API Key here
SPORTSDATA_API_KEY = "f43641c1d2ed44238564427ba6b50a99"

class SportsDataClient:
    """
    Connects to the SportsData.io API for real-time event data via polling.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.sportsdata.io/v3"
        self.logger = get_trading_logger("sportsdata_client")

    def get_live_games_for_sport(self, sport: str = 'nba') -> list:
        """
        Fetches all games that are currently in-progress.
        NOTE: This is a synchronous function.
        """
        # This endpoint gets all scores for the current day.
        # We will filter for only live games.
        url = f"{self.base_url}/{sport}/scores/json/GamesByDate/2025-SEP-19" # Use current date
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

    async def poll_for_updates(self, data_queue: Queue, sport: str = 'nba'):
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
            await asyncio.sleep(5) # Poll every 5 seconds
