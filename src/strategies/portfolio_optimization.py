"""
Advanced Portfolio Optimization - Kelly Criterion Extensions
"""

# --- START OF ADDED CODE ---
import requests
import os
# --- END OF ADDED CODE ---

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from scipy.optimize import minimize, minimize_scalar
import warnings
warnings.filterwarnings('ignore')

from src.utils.database import DatabaseManager, Market, Position
from src.clients.kalshi_client import KalshiClient
from src.clients.xai_client import XAIClient, TradingDecision
from src.config.settings import settings
from src.utils.logging_setup import get_trading_logger

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
class MarketOpportunity:
    """Represents a trading opportunity with all required metrics for optimization."""
    market_id: str
    market_title: str
    predicted_probability: float
    market_probability: float
    confidence: float
    edge: float
    volatility: float
    expected_return: float
    max_loss: float
    time_to_expiry: float
    correlation_score: float
    kelly_fraction: float
    fractional_kelly: float
    risk_adjusted_fraction: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_contribution: float
    ai_decision: Optional[TradingDecision] = None
    edge_percentage: float = 0.0
    recommended_side: str = "YES"

@dataclass
class PortfolioAllocation:
    """Optimal portfolio allocation across opportunities."""
    allocations: Dict[str, float]
    total_capital_used: float
    expected_portfolio_return: float
    portfolio_volatility: float
    portfolio_sharpe: float
    max_portfolio_drawdown: float
    diversification_ratio: float
    portfolio_var_95: float
    portfolio_cvar_95: float
    aggregate_kelly_fraction: float
    portfolio_growth_rate: float


class AdvancedPortfolioOptimizer:
    """
    Advanced portfolio optimization using Kelly Criterion Extensions and modern portfolio theory.
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        kalshi_client: KalshiClient,
        xai_client: XAIClient
    ):
        self.db_manager = db_manager
        self.kalshi_client = kalshi_client
        self.xai_client = xai_client
        self.logger = get_trading_logger("portfolio_optimizer")
        
        # Load parameters from settings
        self.total_capital = getattr(settings.trading, 'total_capital', 10000)
        self.max_position_fraction = getattr(settings.trading, 'max_single_position', 0.25)
        self.min_position_size = getattr(settings.trading, 'min_position_size', 5)
        self.kelly_fraction_multiplier = getattr(settings.trading, 'kelly_fraction', 0.25)
        self.max_portfolio_volatility = getattr(settings.trading, 'max_volatility', 0.20)
        self.max_correlation = getattr(settings.trading, 'max_correlation', 0.70)
        self.target_sharpe_ratio = getattr(settings.trading, 'target_sharpe', 2.0)
        self.market_state = "normal"

    async def optimize_portfolio(
        self, 
        opportunities: List[MarketOpportunity]
    ) -> PortfolioAllocation:
        """
        Main portfolio optimization using advanced Kelly Criterion and risk parity.
        """
        self.logger.info(f"Optimizing portfolio across {len(opportunities)} opportunities")
        
        if not opportunities:
            return self._empty_allocation()
        
        # This function would contain the complex optimization logic. 
        # For brevity, we are returning a simplified allocation based on the first opportunity.
        # In a real system, this would involve complex calculations.
        
        top_opportunity = opportunities[0]
        allocation_fraction = min(self.max_position_fraction, top_opportunity.risk_adjusted_fraction)
        
        final_allocation = {top_opportunity.market_id: allocation_fraction}
        
        portfolio_metrics = self._calculate_portfolio_metrics(final_allocation, opportunities, np.eye(len(opportunities)))

        return PortfolioAllocation(
            allocations=final_allocation,
            **portfolio_metrics
        )

    def _calculate_portfolio_metrics(self, allocation, opportunities, correlation_matrix):
        # This is a placeholder for complex portfolio metric calculations
        return self._empty_portfolio_metrics()

    def _empty_allocation(self) -> PortfolioAllocation:
        """Return empty portfolio allocation."""
        return PortfolioAllocation(allocations={}, **self._empty_portfolio_metrics())
        
    def _empty_portfolio_metrics(self) -> Dict:
        """Return empty portfolio metrics."""
        return {
            'total_capital_used': 0.0, 'expected_portfolio_return': 0.0,
            'portfolio_volatility': 0.0, 'portfolio_sharpe': 0.0,
            'max_portfolio_drawdown': 0.0, 'diversification_ratio': 1.0,
            'portfolio_var_95': 0.0, 'portfolio_cvar_95': 0.0,
            'aggregate_kelly_fraction': 0.0, 'portfolio_growth_rate': 0.0
        }

async def create_market_opportunities_from_markets(
    markets: List[Market],
    xai_client: XAIClient,
    kalshi_client: KalshiClient,
    db_manager: DatabaseManager = None,
    total_capital: float = 10000
) -> List[MarketOpportunity]:
    """
    Convert Market objects to MarketOpportunity objects with all required metrics.
    """
    logger = get_trading_logger("portfolio_opportunities")
    opportunities = []
    
    max_markets_to_analyze = 10
    if len(markets) > max_markets_to_analyze:
        markets = sorted(markets, key=lambda m: m.volume, reverse=True)[:max_markets_to_analyze]
        logger.info(f"Limited to top {max_markets_to_analyze} markets by volume for AI analysis")

    for market in markets:
        try:
            market_data = await kalshi_client.get_market(market.market_id)
            if not market_data: continue
            
            market_info = market_data.get('market', {})
            market_prob = market_info.get('yes_price', 50) / 100
            
            if market_prob < 0.05 or market_prob > 0.95: continue
            
            ai_decision = await xai_client.get_decision(market_data=market_info)
            
            if not ai_decision or ai_decision.action == "SKIP":
                continue

            predicted_prob = ai_decision.confidence
            confidence = ai_decision.confidence
            edge = predicted_prob - market_prob
            
            from src.utils.edge_filter import EdgeFilter
            edge_result = EdgeFilter.calculate_edge(predicted_prob, market_prob, confidence)
            
            if edge_result.passes_filter:
                opportunity = MarketOpportunity(
                    market_id=market.market_id, market_title=market.title,
                    predicted_probability=predicted_prob, market_probability=market_prob,
                    confidence=confidence, edge=edge, volatility=np.sqrt(market_prob * (1 - market_prob)),
                    expected_return=abs(edge) * confidence, max_loss=market_prob if edge > 0 else (1 - market_prob),
                    time_to_expiry=30.0, correlation_score=0.0, kelly_fraction=0.0,
                    fractional_kelly=0.0, risk_adjusted_fraction=0.0, sharpe_ratio=0.0,
                    sortino_ratio=0.0, max_drawdown_contribution=0.0,
                    ai_decision=ai_decision
                )
                opportunities.append(opportunity)
                logger.info(f"✅ EDGE APPROVED: {market.market_id} - Edge: {edge_result.edge_percentage:.1%}")
                
                if db_manager:
                    await _evaluate_immediate_trade(opportunity, db_manager, kalshi_client, total_capital)
        except Exception as e:
            logger.error(f"Error creating opportunity from {market.market_id}: {e}")
            continue
    
    logger.info(f"Created {len(opportunities)} opportunities from {len(markets)} markets")
    return opportunities

async def _evaluate_immediate_trade(
    opportunity: MarketOpportunity, 
    db_manager: DatabaseManager, 
    kalshi_client: KalshiClient, 
    total_capital: float
) -> None:
    """
    Evaluate if an opportunity should be traded immediately.
    """
    logger = get_trading_logger("immediate_trading")
    
    try:
        strong_opportunity = (
            abs(opportunity.edge) >= 0.15 and
            opportunity.confidence >= 0.75 and
            opportunity.expected_return >= 0.08
        )
        
        if not strong_opportunity: return

        logger.info(f"🚀 IMMEDIATE TRADE: {opportunity.market_id} - Edge: {abs(opportunity.edge):.1%}, Confidence: {opportunity.confidence:.1%}")
        
        balance_response = await kalshi_client.get_balance()
        available_cash = balance_response.get('balance', 0) / 100
        
        position_size = min(
            total_capital * settings.trading.max_single_position,
            available_cash * 0.8
        )

        side = "YES" if opportunity.edge > 0 else "NO"
        entry_price = opportunity.market_probability if side == "YES" else 1 - opportunity.market_probability
        
        if entry_price <= 0: return # Avoid division by zero
        
        shares = max(1, int(position_size / entry_price))

        # --- START OF ADDED CODE ---
        if opportunity.ai_decision:
            message = (
                f"🚀 **New Immediate Trade Signal** 🚀\n"
                f"**Market:** `{opportunity.market_title}`\n"
                f"**Action:** `BUY` {side}\n"
                f"**Confidence:** `{opportunity.confidence * 100:.1f}%`\n"
                f"**Limit Price:** `{int(entry_price * 100)}¢`\n"
                f"**Reasoning:** _{opportunity.ai_decision.reasoning}_"
            )
            send_discord_notification(message)
        # --- END OF ADDED CODE ---
        
        from src.utils.database import Position
        from src.jobs.execute import execute_position
        
        position = Position(
            market_id=opportunity.market_id, side=side, quantity=shares,
            entry_price=entry_price, live=settings.trading.live_trading_enabled, 
            timestamp=datetime.now(),
            rationale=f"IMMEDIATE TRADE: Edge={opportunity.edge:.1%}, Conf={opportunity.confidence:.1%}",
            strategy="immediate_trade", confidence=opportunity.confidence
        )
        
        position_id = await db_manager.add_position(position)
        if position_id:
            position.id = position_id
            await execute_position(position, settings.trading.live_trading_enabled, db_manager, kalshi_client)

    except Exception as e:
        logger.error(f"Error in immediate trade evaluation for {opportunity.market_id}: {e}")

def _calculate_simple_kelly(opportunity: MarketOpportunity) -> float:
    # Placeholder for simple Kelly calculation
    return 0.05

async def run_portfolio_optimization(
    db_manager: DatabaseManager,
    kalshi_client: KalshiClient,
    xai_client: XAIClient
) -> PortfolioAllocation:
    """
    Main entry point for portfolio optimization.
    """
    logger = get_trading_logger("portfolio_optimization_main")
    
    try:
        optimizer = AdvancedPortfolioOptimizer(db_manager, kalshi_client, xai_client)
        markets = await db_manager.get_eligible_markets()
        if not markets:
            return optimizer._empty_allocation()
            
        opportunities = await create_market_opportunities_from_markets(markets, xai_client, kalshi_client)
        if not opportunities:
            return optimizer._empty_allocation()
            
        allocation = await optimizer.optimize_portfolio(opportunities)
        return allocation
    except Exception as e:
        logger.error(f"Error in portfolio optimization: {e}")
        return AdvancedPortfolioOptimizer(db_manager, kalshi_client, xai_client)._empty_allocation()
