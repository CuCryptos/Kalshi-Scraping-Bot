# src/jobs/scalp.py

import asyncio
import uuid
from asyncio import Queue
from datetime import datetime
from src.clients.kalshi_client import KalshiClient
from src.utils.logging_setup import get_trading_logger

# --- UPDATED IMPORTS FOR SPORTSDATA.IO ---
from src.clients.sportsdata_client import SportsDataClient, SPORTSDATA_API_KEY


def parse_event_for_trigger(event_data: dict, market: dict) -> dict | None:
    """
    Parses a message from SPORTSDATA.IO to find a trading trigger
    for a specific market.
    """
    market_title = market['title'].lower()

    # The data from the poller is in a 'games' list
    for game in event_data.get("games", []):
        # Normalize team names from the API for reliable matching
        home_team = game.get('HomeTeam', '').lower()
        away_team = game.get('AwayTeam', '').lower()
        
        # Check if this game update is relevant to the market this executor is watching
        if home_team in market_title and away_team in market_title:
            # We found a relevant game! Now, let's log the score.
            # This is the entry point for your proprietary trading logic.
            print(
                f"--- LIVE SCORE UPDATE (SportsData.io) for {market['ticker']} --- | "
                f"{game.get('HomeTeam')} {game.get('HomeScore')} - "
                f"{game.get('AwayScore')} {game.get('AwayTeam')} | "
                f"Quarter: {game.get('Quarter')}, Time Remaining: {game.get('TimeRemainingMinutes')}:{game.get('TimeRemainingSeconds')}"
            )
            
            # --- EXAMPLE TRADING LOGIC ---
            # Here you would analyze the score, time, etc., to decide on a trade.
            # For example: if the home team just took the lead in the 4th quarter...
            # if game.get('HomeScore') > game.get('AwayScore') and game.get('Quarter') == 4:
            #     return {"side_to_buy": "yes"} # Assuming market is "Home Team to Win"
            
    # Return None if no trading condition is met
    return None


async def trade_executor(data_queue: Queue, market: dict, kalshi_client: KalshiClient):
    """
    Listens to the SHARED data queue and executes trades for its assigned market.
    """
    logger = get_trading_logger(f"scalp_executor_{market['ticker']}")
    logger.info("Trade executor is armed and listening to the main data stream.")
    
    while True:
        try:
            # Wait for any new event data from the shared data_streamer queue
            event_data = await data_queue.get()
            
            # Parse the data to see if it's a trigger for THIS specific market
            trigger = parse_event_for_trigger(event_data, market)
            
            if trigger:
                side_to_buy = trigger.get("side_to_buy")
                logger.info(f"TRIGGER! Executing {side_to_buy.upper()} for '{market['title']}'")
                
                # --- Place Market Order ---
                await kalshi_client.place_order(
                    ticker=market['ticker'],
                    client_order_id=str(uuid.uuid4()),
                    action="buy",
                    side=side_to_buy,
                    count=1, # Always start with 1 contract for safety
                    type_="market"
                )
                # NOTE: A more advanced version would also place a take-profit order here.

            data_queue.task_done()
        except Exception as e:
            logger.error(f"Error in trade executor: {e}")


async def run_data_streamer(data_queue: Queue, sport_key: str):
    """
    This is the SINGLE task that polls SportsData.io and streams all data.
    """
    logger = get_trading_logger(f"data_streamer_{sport_key}")
    client = SportsDataClient(api_key=SPORTSDATA_API_KEY)
    
    # This will run forever, feeding data into the queue for all executors
    await client.poll_for_updates(data_queue, sport=sport_key)
