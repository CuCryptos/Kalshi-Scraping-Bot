"""
Enhanced Trading Job - Beast Mode 🚀
"""

# --- START OF ADDED CODE ---
import requests
import os
# --- END OF ADDED CODE ---

import asyncio
import logging
from datetime import datetime
from typing import Optional

from src.clients.kalshi_client import KalshiClient
from src.clients.xai_client import XAIClient, TradingDecision
from src.utils.database import DatabaseManager
from src.config.settings import settings
from src.utils.logging_setup import get_trading_logger

from src.strategies.unified_trading_system import (
    run_unified_trading_system,
    TradingSystemConfig,
    TradingSystemResults
)

from src.jobs.decide import make_decision_for_market
from src.jobs.execute import execute_position

# --- START OF ADDED CODE ---
def send_discord_notification(message: str):
    """Sends a message to the Discord webhook."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    
    payload = {"content": message}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger = get_trading_logger("discord_notifier")
        logger.error(f"Error sending Discord notification: {e}")
# --- END OF ADDED CODE ---


async def run_trading_job() -> Optional[TradingSystemResults]:
    """
    Enhanced trading job using the Unified Advanced Trading System.
    """
    logger = get_trading_logger("trading_job")
    
    try:
        logger.info("🚀 Starting Enhanced Trading Job - Beast Mode Activated!")
        
        db_manager = DatabaseManager()
        kalshi_client = KalshiClient()
        xai_client = XAIClient(db_manager=db_manager)
        
        config = TradingSystemConfig(
            market_making_allocation=getattr(settings.trading, 'market_making_allocation', 0.40),
            directional_trading_allocation=getattr(settings.trading, 'directional_allocation', 0.50),
            arbitrage_allocation=getattr(settings.trading, 'arbitrage_allocation', 0.10),
            max_portfolio_volatility=getattr(settings.trading, 'max_volatility', 0.20),
            max_correlation_exposure=getattr(settings.trading, 'max_correlation', 0.70),
            max_single_position=getattr(settings.trading, 'max_single_position', 0.15),
            target_sharpe_ratio=getattr(settings.trading, 'target_sharpe', 2.0),
            target_annual_return=getattr(settings.trading, 'target_return', 0.30),
            max_drawdown_limit=getattr(settings.trading, 'max_drawdown', 0.15),
            rebalance_frequency_hours=getattr(settings.trading, 'rebalance_hours', 6),
            profit_taking_threshold=getattr(settings.trading, 'profit_threshold', 0.25),
            loss_cutting_threshold=getattr(settings.trading, 'loss_threshold', 0.10)
        )
        
        logger.info("🎯 Executing Unified Advanced Trading System")
        results = await run_unified_trading_system(
            db_manager, kalshi_client, xai_client, config
        )
        
        if results and results.total_positions > 0:
            logger.info(f"✅ TRADING JOB COMPLETE - BEAST MODE RESULTS: {results.total_positions} positions")
        else:
            logger.info("📊 Trading job complete - no new positions created this cycle")
            
        return results
        
    except Exception as e:
        logger.error(f"Error in enhanced trading job: {e}")
        logger.warning("🔄 Falling back to legacy decision-making system")
        return await _fallback_legacy_trading()


async def _fallback_legacy_trading() -> Optional[TradingSystemResults]:
    """
    Fallback to the original sequential decision-making if unified system fails.
    """
    logger = get_trading_logger("trading_job_fallback")
    
    try:
        logger.info("🔄 Executing fallback legacy trading system")
        
        db_manager = DatabaseManager()
        kalshi_client = KalshiClient()
        xai_client = XAIClient()
        
        markets = await db_manager.get_eligible_markets(
            volume_min=20000,
            max_days_to_expiry=365
        )
        if not markets:
            logger.warning("No eligible markets found")
            return TradingSystemResults()
        
        positions_created = 0
        total_exposure = 0.0
        
        for market in markets[:5]:
            try:
                position = await make_decision_for_market(
                    market, db_manager, xai_client, kalshi_client
                )
                
                if position:
                    # --- START OF ADDED CODE ---
                    # Format and send the Discord notification for fallback trades
                    message = (
                        f"Legacy Fallback Trade Signal\n"
                        f"**Market:** `{market.title}`\n"
                        f"**Action:** `BUY` {position.side}\n"
                        f"**Confidence:** `{position.confidence * 100:.1f}%`\n"
                        f"**Limit Price:** `{int(position.entry_price * 100)}¢`\n"
                        f"**Reasoning:** _{position.rationale}_"
                    )
                    send_discord_notification(message)
                    # --- END OF ADDED CODE ---
                    
                    success = await execute_position(position, kalshi_client, db_manager)
                    if success:
                        positions_created += 1
                        total_exposure += position.entry_price * position.quantity
                        logger.info(f"✅ Legacy: Created position for {market.market_id}")
            
            except Exception as e:
                logger.error(f"Error processing market {market.market_id}: {e}")
                continue
        
        return TradingSystemResults(
            directional_positions=positions_created,
            directional_exposure=total_exposure,
            total_capital_used=total_exposure,
            total_positions=positions_created,
            capital_efficiency=total_exposure / 10000 if total_exposure > 0 else 0.0
        )
        
    except Exception as e:
        logger.error(f"Error in fallback trading system: {e}")
        return TradingSystemResults()


# For backwards compatibility
async def run_legacy_trading():
    """Legacy entry point - redirects to enhanced system."""
    logger = get_trading_logger("legacy_redirect")
    logger.info("🔄 Legacy trading call redirected to enhanced system")
    return await run_trading_job()
