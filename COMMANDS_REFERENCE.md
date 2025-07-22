# 🚀 Kalshi Trading System - Commands Reference

Complete reference guide for all commands and operations in the Kalshi automated trading system.

## 📋 **Quick Start Commands**

```bash
# Run the main trading system
python beast_mode_bot.py

# Run tests (interactive menu)
python run_tests.py

# Check current positions
python get_positions.py

# Monitor performance
python beast_mode_dashboard.py
```

---

## 🎯 **Main Trading System**

### **Core Trading Bot**
```bash
# Main beast mode trading system (unified strategy)
python beast_mode_bot.py

# Alternative: Manual trading system runner  
python -c "
import asyncio
from src.jobs.trade import run_unified_trading_system
asyncio.run(run_unified_trading_system())
"
```

### **Individual Job Components**
```bash
# Market data ingestion
python -c "
import asyncio
from src.jobs.ingest import run_ingestion
from src.utils.database import DatabaseManager
async def main():
    db = DatabaseManager()
    await db.initialize()
    queue = asyncio.Queue()
    await run_ingestion(db, queue)
asyncio.run(main())
"

# Decision making for markets
python -c "
import asyncio
from src.jobs.decide import make_decision_for_market
from src.utils.database import DatabaseManager
from src.clients.xai_client import XAIClient
from src.clients.kalshi_client import KalshiClient
# ... (requires market object setup)
"

# Position tracking and exits
python -c "
import asyncio
from src.jobs.track import run_tracking
asyncio.run(run_tracking())
"
```

---

## 🧪 **Testing Commands**

### **Interactive Test Runner**
```bash
# Interactive test menu (recommended)
python run_tests.py

# Options:
# 1. Quick tests (30 seconds - imports, config, database)
# 2. Full tests (2-3 minutes - includes API calls) 
# 3. Custom tests (specify pattern)
```

### **Direct Pytest Commands**
```bash
# Run all tests (may be slow with many API calls)
python -m pytest tests/ -v --tb=short -s

# Quick database tests only
python -m pytest tests/test_database.py -v -s

# Decision engine test (1 market only)
python -m pytest tests/test_decide.py::test_make_decision_for_market_creates_position -v -s

# End-to-end test (optimized)
python -m pytest tests/test_end_to_e2e.py -v -s

# Sell limit order functionality test
python -m pytest tests/test_execute.py::test_sell_limit_order_functionality -v -s
```

### **Import and Configuration Tests**
```bash
# Test all critical imports
python -c "
from src.jobs.decide import make_decision_for_market
from src.jobs.execute import execute_position
from src.jobs.track import run_tracking
from src.jobs.ingest import run_ingestion
print('✅ All imports successful')
"

# Validate configuration
python -c "
from src.config.settings import settings
print(f'Primary model: {settings.trading.primary_model}')
print(f'Max position size: {settings.trading.max_position_size_pct}%')
print(f'Min edge requirement: {settings.trading.min_trade_edge}')
print(f'Kelly fraction: {settings.trading.kelly_fraction}')
"
```

---

## 📊 **Performance Analysis**

### **Automated Performance Analysis**
```bash
# Run automated Grok4 performance analysis
python -c "
import asyncio
from src.jobs.automated_performance_analyzer import AutomatedPerformanceAnalyzer
async def main():
    analyzer = AutomatedPerformanceAnalyzer()
    await analyzer.run_full_analysis()
asyncio.run(main())
"

# Quick performance check
python analyze_performance.py

# Performance system manager
python performance_system_manager.py
```

### **Manual Analysis Scripts**
```bash
# Quick performance analysis
python quick_performance_analysis.py

# Cost monitoring
python cost_monitor.py

# Extract Grok analysis from logs
python extract_grok_analysis.py
```

---

## 💰 **Portfolio Management**

### **Position Monitoring**
```bash
# Get current positions
python get_positions.py

# Check position limits status
python -c "
import asyncio
from src.utils.position_limits import PositionLimitsManager
from src.utils.database import DatabaseManager
from src.clients.kalshi_client import KalshiClient
async def main():
    db = DatabaseManager()
    await db.initialize()
    kalshi = KalshiClient()
    manager = PositionLimitsManager(db, kalshi)
    status = await manager.get_position_limits_status()
    print(f\"Position Status: {status['status']}\")
    print(f\"Usage: {status['position_utilization']}\")
    await kalshi.close()
asyncio.run(main())
"
```

### **Cash Reserves Management**  
```bash
# Check cash reserves status
python -c "
import asyncio
from src.utils.cash_reserves import CashReservesManager
from src.utils.database import DatabaseManager
from src.clients.kalshi_client import KalshiClient
async def main():
    db = DatabaseManager()
    await db.initialize()
    kalshi = KalshiClient()
    manager = CashReservesManager(db, kalshi)
    status = await manager.get_cash_status()
    print(f\"Cash Status: {status['status']}\")
    print(f\"Reserve %: {status['reserve_percentage']:.1f}%\")
    await kalshi.close()
asyncio.run(main())
"
```

---

## 🔧 **Utility Commands**

### **Database Operations**
```bash
# Initialize database
python -c "
import asyncio
from src.utils.database import DatabaseManager
async def main():
    db = DatabaseManager()
    await db.initialize()
    print('Database initialized')
asyncio.run(main())
"

# Get market statistics
python -c "
import asyncio
from src.utils.database import DatabaseManager
async def main():
    db = DatabaseManager()
    await db.initialize()
    markets = await db.get_eligible_markets(volume_min=1000, max_days_to_expiry=365)
    print(f'Eligible markets: {len(markets)}')
asyncio.run(main())
"
```

### **API Client Testing**
```bash
# Test Kalshi API connection
python -c "
import asyncio
from src.clients.kalshi_client import KalshiClient
async def main():
    client = KalshiClient()
    balance = await client.get_balance()
    print(f\"Balance: \${balance.get('balance', 0) / 100:.2f}\")
    await client.close()
asyncio.run(main())
"

# Test XAI (Grok) client
python -c "
import asyncio
from src.clients.xai_client import XAIClient
async def main():
    client = XAIClient()
    print(f\"XAI client initialized with model: {client.primary_model}\")
    await client.close()
asyncio.run(main())
"
```

---

## 🎮 **Interactive Dashboards**

### **Real-time Monitoring**
```bash
# Beast mode dashboard (real-time monitoring)
python beast_mode_dashboard.py

# Performance system dashboard
python performance_system_manager.py
```

---

## ⚙️ **Configuration**

### **View Current Settings**
```bash
# Show all trading configuration
python -c "
from src.config.settings import settings
import json
config_dict = {
    'max_position_size_pct': settings.trading.max_position_size_pct,
    'max_positions': settings.trading.max_positions,
    'min_confidence_to_trade': settings.trading.min_confidence_to_trade,
    'min_volume': settings.trading.min_volume,
    'kelly_fraction': settings.trading.kelly_fraction,
    'max_single_position': settings.trading.max_single_position,
    'primary_model': settings.trading.primary_model,
    'ai_max_tokens': settings.trading.ai_max_tokens
}
print(json.dumps(config_dict, indent=2))
"
```

### **Key Configuration Values** (Updated for Conservative Mode)
```bash
# Current conservative settings:
# - Max position size: 3% (down from 5%)
# - Min confidence: 65% (up from 55%) 
# - Min edge required: 15% (up from 10%)
# - Min volume: 50,000 (up from 20,000)
# - Kelly fraction: 0.5 (down from 0.75)
# - Cash reserves: 1% (down from 15% for full portfolio use)
```

---

## 🚨 **Emergency Commands**

### **Stop Trading**
```bash
# Emergency stop - kill all Python processes
pkill -f "python.*beast_mode"

# Or find and kill specific process
ps aux | grep "beast_mode_bot.py"
kill <PID>
```

### **Emergency Position Review**
```bash
# Quick position and cash check
python -c "
import asyncio
from src.clients.kalshi_client import KalshiClient
async def main():
    client = KalshiClient()
    balance = await client.get_balance()
    positions = await client.get_positions()
    print(f\"💰 Cash: \${balance.get('balance', 0) / 100:.2f}\")
    print(f\"📊 Open positions: {len(positions.get('positions', []))}\")
    await client.close()
asyncio.run(main())
"
```

---

## 📝 **Logging and Debugging**

### **View Recent Logs**
```bash
# View latest trading log
tail -f logs/latest.log

# View recent logs with timestamps
tail -100 logs/latest.log | grep "$(date +%Y-%m-%d)"

# Search for specific events
grep "POSITION" logs/latest.log | tail -10
grep "ERROR" logs/latest.log | tail -10
grep "EDGE FILTERED" logs/latest.log | tail -10
```

### **Performance Analysis Logs**
```bash
# View latest performance analysis
ls -la performance_analysis_*.json | tail -1 | xargs cat | python -m json.tool
```

---

## 🔄 **Automation Setup**

### **Cron Job Example** (Run every 15 minutes)
```bash
# Add to crontab (crontab -e):
*/15 * * * * cd /Users/ryanfrigo/dev/kalshi && /usr/bin/python beast_mode_bot.py >> logs/cron.log 2>&1
```

### **Background Process**
```bash
# Run in background with logging
nohup python beast_mode_bot.py >> logs/beast_mode_background.log 2>&1 &

# Check if still running
ps aux | grep beast_mode_bot.py
```

---

## 📚 **Additional Resources**

- **Main README**: `README.md` - Project overview and setup
- **Performance System**: `README_PERFORMANCE_SYSTEM.md` - Detailed performance analysis docs
- **Configuration**: `src/config/settings.py` - All configurable parameters
- **Test Database**: Uses fixture data in `tests/fixtures/markets.json`

---

## 🆘 **Troubleshooting**

### **Common Issues**
```bash
# If imports fail, check Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# If API calls fail, check credentials
ls -la kalshi_private_key

# If tests hang, use the optimized test runner
python run_tests.py  # Choose option 1 for quick tests

# Clear test databases
rm -f test_*.db e2e_test_*.db
```

### **Reset Everything**
```bash
# Clear all test files and restart
rm -f test_*.db e2e_test_*.db *.log
python run_tests.py  # Choose option 1 to verify everything works
``` 