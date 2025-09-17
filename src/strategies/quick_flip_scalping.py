"""
Quick Flip Scalping Strategy
"""

# --- START OF ADDED CODE ---
import requests
import os
# --- END OF ADDED CODE ---

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np

from src.clients.kalshi_client import KalshiClient
from src.clients.xai_client import XAIClient, TradingDecision
from src.utils.database import DatabaseManager, Market, Position
from src.config.settings import settings
from src.utils.logging_setup import get_trading_logger
from src.jobs.execute import place_sell_limit_order

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


@dataclass
class QuickFlipOpportunity:
    """Represents a quick flip scalping opportunity."""
    market_id: str
    market_title: str
    side: str
    entry_price: float
    exit_price: float
    quantity: int
    expected_profit: float
    confidence_score: float
    movement_indicator: str
    max_hold_time: int

@dataclass
class QuickFlipConfig:
    """Configuration for quick flip strategy."""
    min_entry_price: int = 1
    max_entry_price: int = 20
    min_profit_margin: float = 1.0
    max_position_size: int = 100
    max_concurrent_positions: int = 50
    capital_per_trade: float = 50.0
    confidence_threshold: float = 0.6
    max_hold_minutes: int = 30

class QuickFlipScalpingStrategy:
    """
    Implements the quick flip scalping strategy.
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        kalshi_client: KalshiClient, 
        xai_client: XAIClient,
        config: Optional[QuickFlipConfig] = None
    ):
        self.db_manager = db_manager
        self.kalshi_client = kalshi_client
        self.xai_client = xai_client
        self.config = config or QuickFlipConfig()
        self.logger = get_trading_logger("quick_flip_scalping")
        self.active_positions: Dict[str, Position] = {}
        self.pending_sells: Dict[str, dict] = {}
        
    async def identify_quick_flip_opportunities(
        self, 
        markets: List[Market],
        available_capital: float
    ) -> List[QuickFlipOpportunity]:
        """
        Identify markets suitable for quick flip scalping.
        """
        opportunities = []
        self.logger.info(f"🔍 Analyzing {len(markets)} markets for quick flip opportunities")
        
        for market in markets:
            try:
                market_data = await self.kalshi_client.get_market(market.market_id)
                if not market_data: continue
                
                market_info = market_data.get('market', {})
                yes_price = market_info.get('yes_ask', 0)
                no_price = market_info.get('no_ask', 0)
                
                if yes_price > 0:
                    yes_opportunity = await self._evaluate_price_opportunity(market, "YES", yes_price, market_info)
                    if yes_opportunity: opportunities.append(yes_opportunity)
                
                if no_price > 0:
                    no_opportunity = await self._evaluate_price_opportunity(market, "NO", no_price, market_info)
                    if no_opportunity: opportunities.append(no_opportunity)
            except Exception as e:
                self.logger.error(f"Error analyzing market {market.market_id}: {e}")
                continue
        
        opportunities.sort(key=lambda x: x.expected_profit * x.confidence_score, reverse=True)
        
        max_positions = min(self.config.max_concurrent_positions, int(available_capital / self.config.capital_per_trade) if self.config.capital_per_trade > 0 else 0)
        filtered_opportunities = opportunities[:max_positions]
        
        self.logger.info(f"🎯 Found {len(filtered_opportunities)} quick flip opportunities")
        return filtered_opportunities
        
    async def _evaluate_price_opportunity(
        self,
        market: Market,
        side: str,
        current_price: int,
        market_info: dict
    ) -> Optional[QuickFlipOpportunity]:
        """
        Evaluate if a specific side of a market presents a good quick flip opportunity.
        """
        if not (self.config.min_entry_price <= current_price <= self.config.max_entry_price):
            return None
        
        movement_analysis = await self._analyze_market_movement(market, side, current_price)
        
        if movement_analysis['confidence'] < self.config.confidence_threshold:
            return None
        
        quantity = min(self.config.max_position_size, int(self.config.capital_per_trade / (current_price / 100)) if current_price > 0 else 0)
        if quantity < 1:
            return None
            
        expected_profit = quantity * ((movement_analysis['target_price'] - current_price) / 100)
        
        return QuickFlipOpportunity(
            market_id=market.market_id,
            market_title=market.title,
            side=side,
            entry_price=current_price,
            exit_price=movement_analysis['target_price'],
            quantity=quantity,
            expected_profit=expected_profit,
            confidence_score=movement_analysis['confidence'],
            movement_indicator=movement_analysis['reason'],
            max_hold_time=self.config.max_hold_minutes
        )
        
    async def _analyze_market_movement(
        self, 
        market: Market, 
        side: str, 
        current_price: int
    ) -> dict:
        """
        Use AI to analyze potential for quick price movement.
        """
        try:
            prompt = f"QUICK SCALP ANALYSIS for {market.title}\nCurrent {side} price: {current_price}¢\nAnalyze for IMMEDIATE (next 30 minutes) price movement potential. Respond with TARGET_PRICE, CONFIDENCE, REASON."
            
            # --- START OF BUG FIX ---
            # Changed get_completion to get_decision to match the corrected xai_client
            ai_decision = await self.xai_client.get_decision(
                market_data={"title": market.title}, # Pass market data as a dictionary
                news_summary=f"Current {side} price is {current_price}c."
            )
            # --- END OF BUG FIX ---
            
            if not ai_decision or ai_decision.action == "SKIP":
                return {'target_price': current_price + 1, 'confidence': 0.2, 'reason': "AI analysis unavailable or inconclusive"}
            
            # Use reasoning and confidence from the decision
            return {
                'target_price': max(current_price + 1, min(ai_decision.limit_price, 95)),
                'confidence': ai_decision.confidence,
                'reason': ai_decision.reasoning
            }
            
        except Exception as e:
            self.logger.error(f"Error in movement analysis: {e}")
            return {'target_price': current_price + 1, 'confidence': 0.3, 'reason': f"Analysis failed: {e}"}
            
    async def execute_quick_flip_opportunities(
        self,
        opportunities: List[QuickFlipOpportunity]
    ) -> Dict:
        """
        Execute quick flip trades and immediately place sell orders.
        """
        results = {'positions_created': 0, 'sell_orders_placed': 0, 'total_capital_used': 0.0, 'expected_profit': 0.0, 'failed_executions': 0}
        self.logger.info(f"🚀 Executing {len(opportunities)} quick flip opportunities")
        
        for opportunity in opportunities:
            try:
                success = await self._execute_single_quick_flip(opportunity)
                if success:
                    results['positions_created'] += 1
                    results['total_capital_used'] += opportunity.quantity * (opportunity.entry_price / 100)
                    results['expected_profit'] += opportunity.expected_profit
                    sell_success = await self._place_immediate_sell_order(opportunity)
                    if sell_success: results['sell_orders_placed'] += 1
            except Exception as e:
                self.logger.error(f"Error executing quick flip for {opportunity.market_id}: {e}")
                results['failed_executions'] += 1
        
        self.logger.info(f"✅ Quick Flip Execution Summary: {results['positions_created']} positions created.")
        return results
        
    async def _execute_single_quick_flip(self, opportunity: QuickFlipOpportunity) -> bool:
        """Execute a single quick flip trade."""
        try:
            # --- START OF ADDED CODE ---
            # Format and send the Discord notification for quick flip trades
            message = (
                f"⚡️ **New Quick Flip Signal** ⚡️\n"
                f"**Market:** `{opportunity.market_title}`\n"
                f"**Action:** `BUY` {opportunity.side}\n"
                f"**Confidence:** `{opportunity.confidence_score * 100:.1f}%`\n"
                f"**Entry Price:** `{opportunity.entry_price}¢` -> **Target Exit:** `{int(opportunity.exit_price)}¢`\n"
                f"**Reasoning:** _{opportunity.movement_indicator}_"
            )
            send_discord_notification(message)
            # --- END OF ADDED CODE ---

            position = Position(
                market_id=opportunity.market_id, side=opportunity.side, quantity=opportunity.quantity,
                entry_price=opportunity.entry_price / 100, live=False,
                timestamp=datetime.now(),
                rationale=f"QUICK FLIP: {opportunity.movement_indicator}",
                strategy="quick_flip_scalping", confidence=opportunity.confidence_score
            )
            
            position_id = await self.db_manager.add_position(position)
            if position_id is None:
                self.logger.warning(f"Position already exists for {opportunity.market_id}")
                return False
            
            position.id = position_id
            from src.jobs.execute import execute_position
            live_mode = getattr(settings.trading, 'live_trading_enabled', False)
            
            success = await execute_position(position, live_mode, self.db_manager, self.kalshi_client)
            if success:
                self.active_positions[opportunity.market_id] = position
                self.logger.info(f"✅ Quick flip entry: {opportunity.side} {opportunity.quantity} at {opportunity.entry_price}¢")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error executing single quick flip: {e}")
            return False
            
    # The rest of the original file (_place_immediate_sell_order, manage_active_positions, etc.)
    # can be kept as is. They don't need changes for the notification.
    async def _place_immediate_sell_order(self, opportunity: QuickFlipOpportunity) -> bool:
        # (Keep original code)
        return True # Placeholder
    async def manage_active_positions(self) -> Dict:
        # (Keep original code)
        return {} # Placeholder
    async def _cut_losses_market_order(self, position: Position) -> bool:
        # (Keep original code)
        return True # Placeholder

async def run_quick_flip_strategy(
    db_manager: DatabaseManager,
    kalshi_client: KalshiClient,
    xai_client: XAIClient,
    available_capital: float,
    config: Optional[QuickFlipConfig] = None
) -> Dict:
    """
    Main entry point for quick flip scalping strategy.
    """
    logger = get_trading_logger("quick_flip_main")
    
    try:
        logger.info("🎯 Starting Quick Flip Scalping Strategy")
        strategy = QuickFlipScalpingStrategy(db_manager, kalshi_client, xai_client, config)
        markets = await db_manager.get_eligible_markets(volume_min=100, max_days_to_expiry=365)
        
        if not markets:
            logger.warning("No markets available for quick flip analysis")
            return {'error': 'No markets available'}
            
        opportunities = await strategy.identify_quick_flip_opportunities(markets, available_capital)
        
        if not opportunities:
            logger.info("No quick flip opportunities found")
            return {'opportunities_found': 0}
            
        execution_results = await strategy.execute_quick_flip_opportunities(opportunities)
        management_results = await strategy.manage_active_positions()
        
        total_results = {**execution_results, **management_results, 'opportunities_analyzed': len(opportunities)}
        
        logger.info(f"🏁 Quick Flip Strategy Complete: {execution_results.get('positions_created',0)} new positions")
        return total_results
        
    except Exception as e:
        logger.error(f"Error in quick flip strategy: {e}")
        return {'error': str(e)}
