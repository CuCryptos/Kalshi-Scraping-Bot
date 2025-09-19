# src/jobs/scalp.py

import asyncio
import uuid
from asyncio import Queue
from datetime import datetime
from src.clients.kalshi_client import KalshiClient
from src.utils.logging_setup import get_trading_logger
from src.clients.sports_api_client import SportsAPIClient, ODDS_API_KEY


def parse_event_for_trigger(event_data: dict, market: dict) -> dict | None:
    """
    Parses a message from the live data feed to see if it's a trading trigger
    FOR A SPECIFIC MARKET.
    """
    market_title = market['title'].lower()

    for game in event_data.get("events", []):
        home_team = game.get('home_team', '').lower()
        away_team = game.get('away_team', '').lower()
        
        # Check if this update is for the market this executor is watching
        if home_team in market_title and away_team in market_title:
            last_update = game.get("last_update", {})
            if last_update.get("score_home") is not None:
                print(
                    f"--- RELEVANT SCORE UPDATE for {market['ticker']} --- | "
                    f"{game.get('home_team')} {last_update.get('score_home')} - "
                    f"{last_update.get('score_away')} {game.get('away_team')}"
                )
                # This is where your real trading logic would go.
                # Example: if the underdog scores, return a buy signal.
                # return {"side_to_buy": "yes"}
    return None

async def trade_executor(data_queue: Queue, market: dict, kalshi_client: KalshiClient):
    """
    Listens to a SHARED data queue and executes trades for its assigned market.
    """
    logger = get_trading_logger(f"scalp_executor_{market['ticker']}")
    logger.info("Trade executor is armed and listening to the main data stream.")
    
    while True:
        try:
            # Wait for any new event data from the shared queue
            event_data = await data_queue.get()
            
            # Parse the data to see if it's a trigger for THIS specific market
            trigger = parse_event_for_trigger(event_data, market)
            
            if trigger:
                side_to_buy = trigger.get("side_to_buy")
                logger.info(f"TRIGGER! Executing {side_to_buy.upper()} for '{market['title']}'")
                
                # ... (Order placement logic remains the same) ...
                
            data_queue.task_done()
        except Exception as e:
            logger.error(f"Error in trade executor: {e}")

async def run_data_streamer(data_queue: Queue, sport_key: str):
    """
    This is the SINGLE task that connects to the WebSocket and streams all data.
    """
    logger = get_trading_logger(f"data_streamer_{sport_key}")
    client = SportsAPIClient(api_key=ODDS_API_KEY)
    
    # This will run forever, feeding data into the queue for all executors
    while True:
        await client.listen_for_events(data_queue, sport=sport_key)
        logger.warning("WebSocket disconnected. Attempting to reconnect in 10 seconds...")
        await asyncio.sleep(10)
