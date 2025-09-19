# src/jobs/scalp.py

import asyncio
import uuid
from asyncio import Queue
from datetime import datetime
from src.clients.kalshi_client import KalshiClient
from src.utils.logging_setup import get_trading_logger
from src.clients.sportsdata_client import SportsDataClient, SPORTSDATA_API_KEY

# This dictionary will act as a simple in-memory cache to track scores
game_score_cache = {}


def parse_event_for_trigger(event_data: dict, market: dict) -> dict | None:
    """
    Parses SportsData.io updates to find our baseball late-inning lead change trigger.
    """
    market_title = market['title'].lower()

    for game in event_data.get("games", []):
        game_id = game.get('GameID')
        home_team = game.get('HomeTeam', '').lower()
        away_team = game.get('AwayTeam', '').lower()

        # Ensure this update is for the correct game by checking team names
        if home_team not in market_title and away_team not in market_title:
            continue

        # --- BASEBALL STRATEGY LOGIC ---
        
        current_inning = game.get('Inning')
        home_score = game.get('HomeTeamRuns')
        away_score = game.get('AwayTeamRuns')
        
        previous_score = game_score_cache.get(game_id)

        if current_inning and home_score is not None and previous_score:
            is_late_inning = current_inning >= 7

            home_team_was_behind = previous_score['home'] <= previous_score['away']
            home_team_is_winning = home_score > away_score
            lead_change_occurred = home_team_was_behind and home_team_is_winning

            if is_late_inning and lead_change_occurred:
                # This strategy assumes the market is "Home Team to Win".
                # We are betting AGAINST them, so we buy the "NO" contract.
                print(f"✅ STRATEGY TRIGGERED: Home team took lead in Inning {current_inning}! Betting against them.")
                return {"side_to_buy": "no"}

        # Update the cache with the latest score for this game
        game_score_cache[game_id] = {'home': home_score, 'away': away_score}

    return None


async def trade_executor(data_queue: Queue, market: dict, kalshi_client: KalshiClient):
    """
    Listens to the SHARED data queue and executes trades for its assigned market.
    """
    logger = get_trading_logger(f"scalp_executor_{market['ticker']}")
    logger.info("Trade executor is armed and listening to the main data stream.")
    
    while True:
        try:
            event_data = await data_queue.get()
            trigger = parse_event_for_trigger(event_data, market)
            
            if trigger:
                side_to_buy = trigger.get("side_to_buy")
                logger.info(f"TRIGGER! Executing {side_to_buy.upper()} for '{market['title']}'")
                
                await kalshi_client.place_order(
                    ticker=market['ticker'],
                    client_order_id=str(uuid.uuid4()),
                    action="buy",
                    side=side_to_buy,
                    count=1,
                    type_="market"
                )

            data_queue.task_done()
        except Exception as e:
            logger.error(f"Error in trade executor: {e}")


async def run_data_streamer(data_queue: Queue, sport_key: str):
    """
    This is the SINGLE task that polls SportsData.io and streams all data.
    """
    logger = get_trading_logger(f"data_streamer_{sport_key}")
    client = SportsDataClient(api_key=SPORTSDATA_API_KEY)
    
    await client.poll_for_updates(data_queue, sport=sport_key)
