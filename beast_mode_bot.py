#!/usr/bin/env python3
"""
Beast Mode Trading Bot 🚀

Main entry point for the Unified Advanced Trading System that orchestrates:
- Market Making Strategy (40% allocation)
- Directional Trading with Portfolio Optimization (50% allocation)
- Arbitrage Detection (10% allocation)
- NEW: High-speed scalping mode for live events

Features:
- No time restrictions (trade any deadline)
- Dynamic exit strategies
- Kelly Criterion portfolio optimization
- Real-time risk management
- Market making for spread profits

Usage:
    python beast_mode_bot.py              # Paper trading mode
    python beast_mode_bot.py --live         # Live trading mode
    python beast_mode_bot.py --dashboard    # Live dashboard mode
    python beast_mode_bot.py --scalp        # Master Scalper mode
"""

import asyncio
import argparse
import time
import signal
from datetime import datetime, timedelta
from typing import Optional

# Original imports
from src.jobs.trade import run_trading_job
from src.jobs.ingest import run_ingestion
from src.jobs.track import run_tracking
from src.jobs.evaluate import run_evaluation
from src.utils.logging_setup import setup_logging, get_trading_logger
from src.utils.database import DatabaseManager
from src.config.settings import settings
from src.clients.xai_client import XAIClient
from src.strategies.unified_trading_system import run_unified_trading_system, TradingSystemConfig
from beast_mode_dashboard import BeastModeDashboard

# Imports for new Scalp Mode
from src.clients.kalshi_client import KalshiClient
# Refactored to import the new specific functions from the scalp module
from src.jobs.scalp import run_data_streamer, trade_executor


# --- SCALPER MODE LOGIC ---

def get_strategy_for_market(market_title: str) -> str | None:
    """
    Checks a market title against a list of keywords to find a matching strategy.
    """
    title = market_title.lower()
    
    # Define keywords for each strategy. You can easily add more here!
    strategy_keywords = {
        'sports_play_by_play': [
            'match',           # Catches Tennis, etc.
            'wins by over',    # Catches Football point spreads
            'points scored'    # Catches Over/Under markets
        ],
        'financial_events': [
            'earnings call',   # Catches the Costco market
            'eur/usd'          # Catches Forex markets
        ]
    }

    for strategy, keywords in strategy_keywords.items():
        for keyword in keywords:
            if keyword in title:
                return strategy
                
    return None

async def run_master_scalper_mode():
    """
    The main orchestrator that launches ONE data streamer and MANY trade executors.
    """
    logger = get_trading_logger("master_scalper")
    
    # A single, shared queue for all tasks to communicate
    data_queue = asyncio.Queue()
    
    # --- Launch ONE data streamer for sports ---
    # This connects to The Odds API and feeds the shared queue.
    # You can launch more streamers here for different sports or data sources.
    logger.info("🚀 Launching master data streamer for basketball...")
    asyncio.create_task(run_data_streamer(data_queue, 'basketball_nba'))
    
    active_executors = {}
    
    logger.info("🚀 Master Scalper Mode Activated. Searching for markets...")
    while True:
        try:
            async with KalshiClient() as kalshi_client:
                markets_response = await kalshi_client.get_markets(status="open")
                active_markets = markets_response.get('markets', [])

                for market in active_markets:
                    market_id = market['ticker']
                    
                    if market_id not in active_executors:
                        strategy = get_strategy_for_market(market['title'])
                        
                        # Only launch executors for the strategies we have a data stream for
                        if strategy == 'sports_play_by_play':
                            logger.info(f"✅ Found scalpable market: '{market['title']}'. Launching executor.")
                            
                            # Launch a dedicated trade executor for this market,
                            # listening to the SHARED data queue.
                            task = asyncio.create_task(trade_executor(data_queue, market, kalshi_client))
                            active_executors[market_id] = task
            
            # Clean up any finished executor tasks
            finished_tasks = {mid for mid, task in active_executors.items() if task.done()}
            for mid in finished_tasks:
                logger.info(f"Executor task for {mid} has finished.")
                del active_executors[mid]

            logger.info(f"Scan complete. {len(active_executors)} executors are active. Rescanning for new markets in 60 seconds.")
            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"Error in master scalper loop: {e}")
            await asyncio.sleep(60)


# --- ORIGINAL BEAST MODE BOT CLASS (Unchanged) ---

class BeastModeBot:
    """
    Beast Mode Trading Bot - Advanced Multi-Strategy Trading System 🚀
    """
    
    def __init__(self, live_mode: bool = False, dashboard_mode: bool = False):
        self.live_mode = live_mode
        self.dashboard_mode = dashboard_mode
        self.logger = get_trading_logger("beast_mode_bot")
        self.shutdown_event = asyncio.Event()
        
        settings.trading.live_trading_enabled = live_mode
        settings.trading.paper_trading_mode = not live_mode
        
        self.logger.info(
            f"🚀 Beast Mode Bot initialized - "
            f"Mode: {'LIVE TRADING' if live_mode else 'PAPER TRADING'}"
        )

    async def run_dashboard_mode(self):
        try:
            self.logger.info("🚀 Starting Beast Mode Dashboard Mode")
            dashboard = BeastModeDashboard()
            await dashboard.show_live_dashboard()
        except KeyboardInterrupt:
            self.logger.info("👋 Dashboard mode stopped")
        except Exception as e:
            self.logger.error(f"Error in dashboard mode: {e}")

    async def run_trading_mode(self):
        try:
            self.logger.info("🚀 BEAST MODE TRADING BOT STARTED")
            self.logger.info(f"📊 Trading Mode: {'LIVE' if self.live_mode else 'PAPER'}")
            self.logger.info(f"💰 Daily AI Budget: ${settings.trading.daily_ai_budget}")
            self.logger.info(f"⚡ Features: Market Making + Portfolio Optimization + Dynamic Exits")
            
            self.logger.info("🔧 Initializing database...")
            db_manager = DatabaseManager()
            await self._ensure_database_ready(db_manager)
            self.logger.info("✅ Database initialization complete!")
            
            kalshi_client = KalshiClient()
            xai_client = XAIClient(db_manager=db_manager)
            
            await asyncio.sleep(1)
            
            self.logger.info("🔄 Starting market ingestion...")
            ingestion_task = asyncio.create_task(self._run_market_ingestion(db_manager, kalshi_client))
            
            await asyncio.sleep(10)
            
            self.logger.info("🚀 Starting trading and monitoring tasks...")
            tasks = [
                ingestion_task,
                asyncio.create_task(self._run_trading_cycles(db_manager, kalshi_client, xai_client)),
                asyncio.create_task(self._run_position_tracking(db_manager, kalshi_client)),
                asyncio.create_task(self._run_performance_evaluation(db_manager))
            ]
            
            def signal_handler():
                self.logger.info("🛑 Shutdown signal received")
                self.shutdown_event.set()
                for task in tasks:
                    task.cancel()
            
            for sig in [signal.SIGINT, signal.SIGTERM]:
                signal.signal(sig, lambda s, f: signal_handler())
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            await xai_client.close()
            await kalshi_client.close()
            
            self.logger.info("🏁 Beast Mode Bot shut down gracefully")
            
        except Exception as e:
            self.logger.error(f"Error in Beast Mode Bot: {e}")
            raise

    async def _ensure_database_ready(self, db_manager: DatabaseManager):
        try:
            await db_manager.initialize()
            
            import aiosqlite
            async with aiosqlite.connect(db_manager.db_path) as db:
                await db.execute("SELECT COUNT(*) FROM positions LIMIT 1")
                await db.execute("SELECT COUNT(*) FROM markets LIMIT 1") 
                await db.execute("SELECT COUNT(*) FROM trade_logs LIMIT 1")
            
            self.logger.info("🎯 Database tables verified and ready")
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            raise

    async def _run_market_ingestion(self, db_manager: DatabaseManager, kalshi_client: KalshiClient):
        while not self.shutdown_event.is_set():
            try:
                market_queue = asyncio.Queue()
                await run_ingestion(db_manager, market_queue)
                await asyncio.sleep(300)
            except Exception as e:
                self.logger.error(f"Error in market ingestion: {e}")
                await asyncio.sleep(60)

    async def _run_trading_cycles(self, db_manager: DatabaseManager, kalshi_client: KalshiClient, xai_client: XAIClient):
        cycle_count = 0
        while not self.shutdown_event.is_set():
            try:
                if not await self._check_daily_ai_limits(xai_client):
                    await self._sleep_until_next_day()
                    continue
                
                cycle_count += 1
                self.logger.info(f"🔄 Starting Beast Mode Trading Cycle #{cycle_count}")
                
                results = await run_trading_job()
                
                if results and results.total_positions > 0:
                    self.logger.info(
                        f"✅ Cycle #{cycle_count} Complete - "
                        f"Positions: {results.total_positions}, "
                        f"Capital Used: ${results.total_capital_used:.0f} ({results.capital_efficiency:.1%}), "
                        f"Expected Return: {results.expected_annual_return:.1%}"
                    )
                else:
                    self.logger.info(f"📊 Cycle #{cycle_count} Complete - No new positions created")
                
                await asyncio.sleep(60)
                
            except Exception as e:
                self.logger.error(f"Error in trading cycle #{cycle_count}: {e}")
                await asyncio.sleep(60)

    async def _check_daily_ai_limits(self, xai_client: XAIClient) -> bool:
        if not settings.trading.enable_daily_cost_limiting:
            return True
        
        if hasattr(xai_client, 'daily_tracker') and xai_client.daily_tracker.is_exhausted:
            self.logger.warning("🚫 Daily AI cost limit reached - trading paused",
                daily_cost=xai_client.daily_tracker.total_cost,
                daily_limit=xai_client.daily_tracker.daily_limit,
                requests_today=xai_client.daily_tracker.request_count
            )
            return False
        
        return True

    async def _sleep_until_next_day(self):
        if not settings.trading.sleep_when_limit_reached:
            await asyncio.sleep(60)
            return
        
        now = datetime.now()
        next_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        seconds_until_next_day = (next_day - now).total_seconds()
        
        max_sleep = 24 * 60 * 60
        sleep_time = min(seconds_until_next_day, max_sleep)
        
        if sleep_time > 0:
            hours_to_sleep = sleep_time / 3600
            self.logger.info(f"💤 Sleeping until next day to reset AI limits - {hours_to_sleep:.1f} hours")
            
            chunk_size = 300
            while sleep_time > 0 and not self.shutdown_event.is_set():
                current_chunk = min(chunk_size, sleep_time)
                await asyncio.sleep(current_chunk)
                sleep_time -= current_chunk
            
            self.logger.info("🌅 Daily AI limits reset - resuming trading")
        else:
            await asyncio.sleep(60)

    async def _run_position_tracking(self, db_manager: DatabaseManager, kalshi_client: KalshiClient):
        while not self.shutdown_event.is_set():
            try:
                await run_tracking(db_manager)
                await asyncio.sleep(120)
            except Exception as e:
                self.logger.error(f"Error in position tracking: {e}")
                await asyncio.sleep(30)

    async def _run_performance_evaluation(self, db_manager: DatabaseManager):
        while not self.shutdown_event.is_set():
            try:
                await run_evaluation()
                await asyncio.sleep(300)
            except Exception as e:
                self.logger.error(f"Error in performance evaluation: {e}")
                await asyncio.sleep(300)

    async def run(self):
        if self.dashboard_mode:
            await self.run_dashboard_mode()
        else:
            await self.run_trading_mode()


# --- UPDATED MAIN FUNCTION WITH ROUTING LOGIC ---

async def main():
    """Main entry point with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Beast Mode Trading Bot 🚀 - Advanced Multi-Strategy Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python beast_mode_bot.py                 # Paper trading mode
  python beast_mode_bot.py --live            # Live trading mode 
  python beast_mode_bot.py --dashboard       # Live dashboard mode
  python beast_mode_bot.py --scalp           # Master Scalper mode
  python beast_mode_bot.py --live --log-level DEBUG # Live mode with debug logs

Beast Mode Features:
  • Market Making (40% allocation) - Profit from spreads
  • Directional Trading (50% allocation) - AI predictions with portfolio optimization
  • Arbitrage Detection (10% allocation) - Cross-market opportunities
  • No time restrictions - Trade any deadline with dynamic exits
  • Kelly Criterion portfolio optimization
  • Real-time risk management and rebalancing
  • Cost controls and budget management
        """
    )
    
    parser.add_argument("--live", action="store_true", help="Run in LIVE trading mode (default: paper trading)")
    parser.add_argument("--dashboard", action="store_true", help="Run in live dashboard mode for monitoring")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Set the logging level (default: INFO)")
    parser.add_argument("--scalp", action="store_true", help="Run in high-speed Master Scalper mode")
    
    args = parser.parse_args()
    
    setup_logging(log_level=args.log_level)
    
    if args.scalp:
        await run_master_scalper_mode()
    else:
        if args.live and not args.dashboard:
            print("⚠️  WARNING: LIVE TRADING MODE ENABLED")
            print("💰 This will use real money and place actual trades!")
            print("🚀 LIVE TRADING MODE CONFIRMED")
        
        bot = BeastModeBot(live_mode=args.live, dashboard_mode=args.dashboard)
        await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Beast Mode Bot stopped by user")
    except Exception as e:
        print(f"❌ Beast Mode Bot error: {e}")
        raise
