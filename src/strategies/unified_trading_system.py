"""
Unified Advanced Trading System - The Beast Mode 🚀
"""

# --- START OF ADDED CODE ---
import requests
import os
# --- END OF ADDED CODE ---

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import numpy as np

from src.clients.kalshi_client import KalshiClient
from src.clients.xai_client import XAIClient, TradingDecision
from src.utils.database import DatabaseManager, Market, Position
from src.config.settings import settings
from src.utils.logging_setup import get_trading_logger

from src.strategies.market_making import (
    AdvancedMarketMaker, 
    MarketMakingOpportunity,
    run_market_making_strategy
)
from src.strategies.portfolio_optimization import (
    AdvancedPortfolioOptimizer, 
    MarketOpportunity, 
    PortfolioAllocation,
    run_portfolio_optimization,
    create_market_opportunities_from_markets
)
from src.strategies.quick_flip_scalping import (
    run_quick_flip_strategy,
    QuickFlipConfig
)

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
class TradingSystemConfig:
    """Configuration for the unified trading system."""
    market_making_allocation: float = 0.30
    directional_trading_allocation: float = 0.40
    quick_flip_allocation: float = 0.30
    arbitrage_allocation: float = 0.00
    max_portfolio_volatility: float = 0.20
    max_correlation_exposure: float = 0.70
    max_single_position: float = 0.15
    target_sharpe_ratio: float = 2.0
    target_annual_return: float = 0.30
    max_drawdown_limit: float = 0.15
    rebalance_frequency_hours: int = 6
    profit_taking_threshold: float = 0.25
    loss_cutting_threshold: float = 0.10

@dataclass
class TradingSystemResults:
    """Results from unified trading system execution."""
    market_making_orders: int = 0
    market_making_exposure: float = 0.0
    market_making_expected_profit: float = 0.0
    directional_positions: int = 0
    directional_exposure: float = 0.0
    directional_expected_return: float = 0.0
    total_capital_used: float = 0.0
    portfolio_expected_return: float = 0.0
    portfolio_sharpe_ratio: float = 0.0
    portfolio_volatility: float = 0.0
    max_portfolio_drawdown: float = 0.0
    correlation_score: float = 0.0
    diversification_ratio: float = 0.0
    total_positions: int = 0
    capital_efficiency: float = 0.0
    expected_annual_return: float = 0.0

class UnifiedAdvancedTradingSystem:
    def __init__(
        self,
        db_manager: DatabaseManager,
        kalshi_client: KalshiClient,
        xai_client: XAIClient,
        config: Optional[TradingSystemConfig] = None
    ):
        self.db_manager = db_manager
        self.kalshi_client = kalshi_client
        self.xai_client = xai_client
        self.config = config or TradingSystemConfig()
        self.logger = get_trading_logger("unified_trading_system")
        self.total_capital = 100
        self.last_rebalance = datetime.now()
        self.system_metrics = {}

    async def async_initialize(self):
        try:
            balance_response = await self.kalshi_client.get_balance()
            available_cash = balance_response.get('balance', 0) / 100
            positions_response = await self.kalshi_client.get_positions()
            positions = positions_response.get('positions', []) if isinstance(positions_response, dict) else []
            total_position_value = 0
            if positions:
                for position in positions:
                    if not isinstance(position, dict): continue
                    quantity = position.get('quantity', 0)
                    market_id = position.get('market_id')
                    if market_id and quantity != 0:
                        try:
                            market_data = await self.kalshi_client.get_market(market_id)
                            market_info = market_data.get('market', {})
                            price_key = 'yes_price' if position.get('side') == 'yes' else 'no_price'
                            current_price = market_info.get(price_key, 50) / 100
                            total_position_value += abs(quantity) * current_price
                        except:
                            total_position_value += abs(quantity) * 0.50
            self.total_capital = available_cash + total_position_value
            self.logger.info(f"💰 PORTFOLIO VALUE: Cash=${available_cash:.2f} + Positions=${total_position_value:.2f} = Total=${self.total_capital:.2f}")
        except Exception as e:
            self.logger.error(f"Failed to get portfolio value, using default: {e}")
            self.total_capital = 100
        
        self.market_making_capital = self.total_capital * self.config.market_making_allocation
        self.directional_capital = self.total_capital * self.config.directional_trading_allocation
        self.quick_flip_capital = self.total_capital * self.config.quick_flip_allocation
        self.arbitrage_capital = self.total_capital * self.config.arbitrage_allocation
        self.market_maker = AdvancedMarketMaker(self.db_manager, self.kalshi_client, self.xai_client)
        self.portfolio_optimizer = AdvancedPortfolioOptimizer(self.db_manager, self.kalshi_client, self.xai_client)
        self.logger.info(f"🎯 CAPITAL ALLOCATION: Market Making=${self.market_making_capital:.2f}, Directional=${self.directional_capital:.2f}, Quick Flip=${self.quick_flip_capital:.2f}")

    async def execute_unified_trading_strategy(self) -> TradingSystemResults:
        self.logger.info("🚀 Executing Unified Advanced Trading Strategy")
        try:
            from src.utils.position_limits import PositionLimitsManager
            from src.utils.cash_reserves import CashReservesManager
            limits_manager = PositionLimitsManager(self.db_manager, self.kalshi_client)
            cash_manager = CashReservesManager(self.db_manager, self.kalshi_client)
            limits_status = await limits_manager.get_position_limits_status()
            self.logger.info(f"📊 POSITION LIMITS STATUS: {limits_status['status']} ({limits_status['position_utilization']})")
            cash_status = await cash_manager.get_cash_status()
            self.logger.info(f"💰 CASH RESERVES STATUS: {cash_status['status']} ({cash_status['reserve_percentage']:.1f}%)")
            
            if cash_status.get('emergency_status'):
                self.logger.warning(f"🚨 CASH EMERGENCY: {cash_status['recommendations']}")
                emergency_action = await cash_manager.handle_cash_emergency()
                if emergency_action.action_type == 'halt_trading':
                    self.logger.critical(f"🛑 TRADING HALTED DUE TO CASH EMERGENCY: {emergency_action.reason}")
                    return TradingSystemResults()

            markets = await self.db_manager.get_eligible_markets(volume_min=200, max_days_to_expiry=365)
            if not markets:
                self.logger.warning("No markets available for trading")
                return TradingSystemResults()
            
            self.logger.info(f"Analyzing {len(markets)} markets across all strategies")
            
            market_making_results, portfolio_allocation, quick_flip_results = await asyncio.gather(
                self._execute_market_making_strategy(markets),
                self._execute_directional_trading_strategy(markets),
                self._execute_quick_flip_strategy(markets)
            )
            
            arbitrage_results = await self._execute_arbitrage_strategy(markets)
            results = self._compile_unified_results(market_making_results, portfolio_allocation, quick_flip_results, arbitrage_results)
            
            await self._manage_risk_and_rebalance(results)
            self.logger.info(f"🎯 Unified Strategy Complete: Positions: {results.total_positions}")
            return results
        except Exception as e:
            self.logger.error(f"Error in unified trading strategy: {e}")
            return TradingSystemResults()

    async def _execute_market_making_strategy(self, markets: List[Market]) -> Dict:
        try:
            self.logger.info(f"🎯 Executing Market Making Strategy on {len(markets)} markets")
            opportunities = await self.market_maker.analyze_market_making_opportunities(markets)
            if not opportunities:
                self.logger.warning("No market making opportunities found")
                return {'orders_placed': 0, 'expected_profit': 0.0}
            max_opportunities = int(self.market_making_capital / 100)
            top_opportunities = opportunities[:max_opportunities]
            results = await self.market_maker.execute_market_making_strategy(top_opportunities)
            self.logger.info(f"✅ Market Making: {results['orders_placed']} orders, ${results['expected_profit']:.2f} expected profit")
            return results
        except Exception as e:
            self.logger.error(f"Error in market making strategy: {e}")
            return {'orders_placed': 0, 'expected_profit': 0.0}

    async def _execute_directional_trading_strategy(self, markets: List[Market]) -> PortfolioAllocation:
        try:
            self.logger.info(f"🎯 Executing Directional Trading Strategy")
            opportunities = await create_market_opportunities_from_markets(
                markets, self.xai_client, self.kalshi_client, 
                self.db_manager, self.directional_capital
            )
            if not opportunities:
                self.logger.warning("No directional trading opportunities found")
                return self.portfolio_optimizer._empty_allocation()
                
            self.portfolio_optimizer.total_capital = self.directional_capital
            allocation = await self.portfolio_optimizer.optimize_portfolio(opportunities)

            if allocation and allocation.allocations:
                execution_results = await self._execute_portfolio_allocations(allocation, opportunities)
                self.logger.info(f"Executed {execution_results['positions_created']} positions from portfolio.")
            
            return allocation
        except Exception as e:
            self.logger.error(f"Error in directional trading strategy: {e}")
            return self.portfolio_optimizer._empty_allocation()

    async def _execute_quick_flip_strategy(self, markets: List[Market]) -> Dict:
        try:
            self.logger.info(f"🎯 Executing Quick Flip Scalping Strategy")
            quick_flip_config = QuickFlipConfig()
            results = await run_quick_flip_strategy(
                db_manager=self.db_manager, kalshi_client=self.kalshi_client, 
                xai_client=self.xai_client, available_capital=self.quick_flip_capital, 
                config=quick_flip_config
            )
            self.logger.info(f"✅ Quick Flip: {results.get('positions_created', 0)} positions")
            return results
        except Exception as e:
            self.logger.error(f"Error in quick flip strategy: {e}")
            return {}

    async def _execute_portfolio_allocations(self, allocation: PortfolioAllocation, opportunities: List[MarketOpportunity]) -> Dict:
        results = {'positions_created': 0, 'total_capital_used': 0.0}
        try:
            from src.jobs.execute import execute_position
            for market_id, allocation_fraction in allocation.allocations.items():
                try:
                    opportunity = next((opp for opp in opportunities if opp.market_id == market_id), None)
                    if not opportunity: continue

                    intended_side = "YES" if opportunity.edge > 0 else "NO"
                    
                    # --- START OF DISCORD NOTIFICATION CODE ---
                    # Format and send the Discord notification
                    if opportunity.ai_decision and opportunity.ai_decision.action != "SKIP":
                        message = (
                            f"🚀 **New AI Trade Signal** 🚀\n"
                            f"**Market:** `{opportunity.title}`\n"
                            f"**Action:** `BUY` {intended_side}\n"
                            f"**Confidence:** `{opportunity.confidence * 100:.1f}%`\n"
                            f"**Reasoning:** _{opportunity.ai_decision.reasoning}_"
                        )
                        send_discord_notification(message)
                    # --- END OF DISCORD NOTIFICATION CODE ---
                    
                    position_value = allocation_fraction * self.directional_capital
                    market_data = await self.kalshi_client.get_market(market_id)
                    market_info = market_data.get('market', {})
                    price = market_info.get('yes_price' if intended_side == "YES" else 'no_price', 50) / 100
                    quantity = max(1, int(position_value / price)) if price > 0 else 1
                    
                    position = Position(
                        market_id=market_id, side=intended_side, entry_price=price, quantity=quantity,
                        timestamp=datetime.now(), rationale=f"Portfolio Allocation: {allocation_fraction:.1%} capital.",
                        confidence=opportunity.confidence, live=settings.trading.live_trading_enabled,
                        strategy="portfolio_optimization"
                    )
                    
                    position_id = await self.db_manager.add_position(position)
                    if position_id:
                        position.id = position_id
                        success = await execute_position(position, settings.trading.live_trading_enabled, self.db_manager, self.kalshi_client)
                        if success:
                            results['positions_created'] += 1
                            results['total_capital_used'] += position_value
                except Exception as e:
                    self.logger.error(f"Error executing allocation for {market_id}: {e}")
            return results
        except Exception as e:
            self.logger.error(f"Error in portfolio allocation execution: {e}")
            return results
    
    async def _execute_arbitrage_strategy(self, markets: List[Market]) -> Dict:
        self.logger.info("🎯 Arbitrage opportunities analysis (future feature)")
        return {}

    def _compile_unified_results(self, market_making_results: Dict, portfolio_allocation: PortfolioAllocation, quick_flip_results: Dict, arbitrage_results: Dict) -> TradingSystemResults:
        try:
            total_capital_used = (market_making_results.get('total_exposure', 0) + portfolio_allocation.total_capital_used)
            capital_efficiency = total_capital_used / self.total_capital if self.total_capital > 0 else 0
            total_positions = market_making_results.get('orders_placed', 0) // 2 + len(portfolio_allocation.allocations)
            
            return TradingSystemResults(
                market_making_orders=market_making_results.get('orders_placed', 0),
                directional_positions=len(portfolio_allocation.allocations),
                total_capital_used=total_capital_used,
                portfolio_sharpe_ratio=portfolio_allocation.portfolio_sharpe,
                total_positions=total_positions,
                capital_efficiency=capital_efficiency
            )
        except Exception as e:
            self.logger.error(f"Error compiling results: {e}")
            return TradingSystemResults()

    async def _manage_risk_and_rebalance(self, results: TradingSystemResults):
        # Placeholder for future risk management logic
        pass

async def run_unified_trading_system(
    db_manager: DatabaseManager,
    kalshi_client: KalshiClient,
    xai_client: XAIClient,
    config: Optional[TradingSystemConfig] = None
) -> TradingSystemResults:
    logger = get_trading_logger("unified_trading_main")
    try:
        logger.info("🚀 Starting Unified Advanced Trading System")
        trading_system = UnifiedAdvancedTradingSystem(db_manager, kalshi_client, xai_client, config)
        await trading_system.async_initialize()
        results = await trading_system.execute_unified_trading_strategy()
        logger.info(f"🎯 UNIFIED SYSTEM COMPLETE - Positions: {results.total_positions}")
        return results
    except Exception as e:
        logger.error(f"Error in unified trading system: {e}")
        return TradingSystemResults()
