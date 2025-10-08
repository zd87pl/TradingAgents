from tradingagents.graph.trading_graph import TradingAgentsGraph
from config import get_unified_config, validate_config
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the unified configuration
config = get_unified_config()

# Validate configuration
try:
    validate_config()
except ValueError as e:
    print(f"Configuration error: {e}")
    exit(1)

# Override any settings for this session if needed
config["deep_think_llm"] = "gpt-4o-mini"  # Use a different model
config["quick_think_llm"] = "gpt-4o-mini"  # Use a different model
config["max_debate_rounds"] = 1  # Debate rounds

# Initialize with unified config
ta = TradingAgentsGraph(debug=True, config=config)

# Get portfolio tickers from unified config
PORTFOLIO_TICKERS = config["portfolio_tickers"]

# Analyze your largest position (AVGO - 43 shares)
print("Analyzing AVGO (Broadcom) - Your largest position...")
_, decision = ta.propagate("AVGO", "2024-10-01")
print("\n" + "="*60)
print("AVGO Analysis Result:")
print("="*60)
print(decision)

# Uncomment below to analyze all positions:
# for ticker in PORTFOLIO_TICKERS:
#     print(f"\nAnalyzing {ticker}...")
#     _, decision = ta.propagate(ticker, "2024-10-01")
#     print(f"{ticker} Decision: {decision[:200]}...")  # First 200 chars

# Memorize mistakes and reflect
# ta.reflect_and_remember(1000) # parameter is the position returns
