"""
XAI client for AI-powered trading decisions.
This is the final, corrected version that fixes all bugs.
"""

import asyncio
import json
import os
import pickle
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from json_repair import repair_json
from xai_sdk import AsyncClient
from xai_sdk.chat import user as xai_user

from src.config.settings import settings
from src.utils.logging_setup import TradingLoggerMixin

@dataclass
class TradingDecision:
    """Represents a structured AI trading decision."""
    action: str = "SKIP"
    side: str = "YES"
    confidence: float = 0.0
    limit_price: int = 50
    reasoning: str = "No decision could be made."

@dataclass
class DailyUsageTracker:
    """Tracks daily AI usage and costs."""
    date: str
    total_cost: float = 0.0
    request_count: int = 0
    daily_limit: float = 50.0
    is_exhausted: bool = False

class XAIClient(TradingLoggerMixin):
    """
    A robust client for interfacing with the xAI API (Grok) for trading decisions.
    """

    def __init__(self, db_manager=None):
        self.api_key = settings.api.xai_api_key
        self.db_manager = db_manager
        self.client = AsyncClient(api_key=self.api_key, timeout=300.0)
        self.primary_model = settings.trading.primary_model
        self.usage_file_path = "logs/daily_ai_usage.pkl"
        self.daily_tracker = self._load_or_create_daily_tracker()
        self.logger.info(
            "xAI client initialized",
            primary_model=self.primary_model,
            daily_limit=self.daily_tracker.daily_limit,
            today_cost=self.daily_tracker.total_cost
        )

    def _load_or_create_daily_tracker(self) -> DailyUsageTracker:
        today_str = datetime.now().strftime("%Y-%m-%d")
        current_limit = settings.trading.daily_ai_cost_limit
        if os.path.exists(self.usage_file_path):
            try:
                with open(self.usage_file_path, 'rb') as f:
                    tracker = pickle.load(f)
                if tracker.date != today_str:
                    return DailyUsageTracker(date=today_str, daily_limit=current_limit)
                tracker.daily_limit = current_limit
                return tracker
            except Exception as e:
                self.logger.warning(f"Could not load usage tracker file, creating new. Reason: {e}")
        return DailyUsageTracker(date=today_str, daily_limit=current_limit)

    def _save_daily_tracker(self):
        try:
            os.makedirs("logs", exist_ok=True)
            with open(self.usage_file_path, 'wb') as f:
                pickle.dump(self.daily_tracker, f)
        except Exception as e:
            self.logger.error(f"Failed to save daily tracker: {e}")

    def _update_cost(self, cost: float):
        self.daily_tracker.total_cost += cost
        self.daily_tracker.request_count += 1
        if not self.daily_tracker.is_exhausted and self.daily_tracker.total_cost >= self.daily_tracker.daily_limit:
            self.daily_tracker.is_exhausted = True
            self.logger.warning("Daily AI cost limit has been reached!",
                                daily_cost=self.daily_tracker.total_cost,
                                daily_limit=self.daily_tracker.daily_limit)
        self._save_daily_tracker()

    async def get_decision(self, market_data: Optional[Dict] = None, news_summary: str = "", **kwargs) -> TradingDecision:
        """
        Gets a trading decision from the AI. Returns a structured TradingDecision object.
        """
        if isinstance(market_data, str):
            market_data = {"title": market_data}
        if market_data is None:
            market_data = {}

        if settings.trading.enable_daily_cost_limiting and self.daily_tracker.is_exhausted:
            self.logger.info("AI analysis skipped due to daily cost limit.")
            return TradingDecision(reasoning="Daily AI cost limit reached.")

        prompt = self._create_trading_prompt(market_data, news_summary)
        messages = [xai_user(prompt)]
        
        response_text, cost = await self._make_api_call(messages)
        
        if response_text is None:
            return TradingDecision(reasoning="API call failed after retries.")
        
        self._update_cost(cost)
        
        parsed_decision = self._parse_response(response_text)
        return parsed_decision if parsed_decision is not None else TradingDecision(reasoning="Failed to parse AI response.")

    async def _make_api_call(self, messages: List, max_retries: int = 2) -> Tuple[Optional[str], float]:
        for attempt in range(max_retries):
            try:
                chat = self.client.chat.create(
                    model=self.primary_model,
                    temperature=settings.trading.ai_temperature,
                    max_tokens=settings.trading.ai_max_tokens
                )
                for message in messages:
                    chat.append(message)
                response = await chat.sample()
                if not response.content or not response.content.strip():
                    raise ValueError("Received empty response from API.")
                tokens_used = getattr(response.usage, 'total_tokens', 1000)
                cost = (tokens_used / 1_000_000) * 10.0
                return response.content, cost
            except Exception as e:
                self.logger.warning(f"xAI API call attempt {attempt + 1} failed: {e}")
                if "resource_exhausted" in str(e).lower() or "rate limit" in str(e).lower():
                    self.logger.error("xAI API rate limit or resource exhaustion error.")
                    return None, 0.0
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        self.logger.error("xAI API call failed after all retries.")
        return None, 0.0

    def _create_trading_prompt(self, market_data: Dict, news_summary: str) -> str:
        from src.utils.prompts import MULTI_AGENT_PROMPT_TPL
        prompt_data = {
            'title': 'N/A', 'rules': 'N/A', 'yes_price': 50, 'no_price': 50,
            'volume': 0, 'days_to_expiry': 'N/A', 'cash': 1000, 
            'max_trade_value': 100, 'max_position_pct': 5, 'ev_threshold': 10,
            **market_data,
            'news_summary': news_summary or "No recent news available."
        }
        return MULTI_AGENT_PROMPT_TPL.format(**prompt_data)

    def _parse_response(self, response_text: str) -> Optional[TradingDecision]:
        try:
            json_str_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_str_match:
                self.logger.warning("No JSON object found in AI response.")
                return None
            repaired_json_str = repair_json(json_str_match.group(0))
            data = json.loads(repaired_json_str)
            action = data.get("action", "SKIP").upper()
            if action not in ["BUY", "SELL", "SKIP"]: action = "SKIP"
            return TradingDecision(
                action=action, side=data.get("side", "YES").upper(),
                confidence=float(data.get("confidence", 0.0)),
                limit_price=int(data.get("limit_price", 50)),
                reasoning=data.get("reasoning", "No reasoning provided.")
            )
        except Exception as e:
            self.logger.error(f"Failed to parse AI JSON response: {e}", raw_response=response_text[:500])
            return None

    async def close(self):
        self.logger.info("xAI client shut down.")
