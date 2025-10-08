#!/usr/bin/env python
"""
Clean Perplexity AI Investment Research Demo
Direct API calls that work without complex imports
"""

import asyncio
import os
import aiohttp
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def call_perplexity(prompt: str, system_prompt: str = None) -> str:
    """Make a direct call to Perplexity API"""

    api_key = os.getenv('PERPLEXITY_API_KEY')
    if not api_key:
        return "Error: No API key"

    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    if not system_prompt:
        system_prompt = "You are a financial analyst. Provide specific, actionable insights with numbers."

    payload = {
        "model": "sonar",  # Working model
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 800,
        "temperature": 0.3
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data['choices'][0]['message']['content']
            else:
                return f"Error: API returned status {response.status}"


async def demo_stock_analysis():
    """Demo 1: Analyze individual stocks"""
    print("\n" + "="*60)
    print("📊 DEMO 1: AI Stock Analysis")
    print("="*60)

    # Analyze NVIDIA
    prompt = """Analyze NVIDIA (NVDA) stock:
    - Current price and P/E ratio
    - Fair value estimate
    - Bull and bear case (brief)
    - Buy/Hold/Sell recommendation
    - Key risks (top 3)
    Be specific with numbers."""

    print("\n🤖 Analyzing NVIDIA (NVDA)...")
    response = await call_perplexity(prompt)
    print(f"\n{response}")

    # Analyze Apple
    print("\n" + "-"*40)
    prompt2 = "Give me a quick analysis of Apple (AAPL) stock: current price, P/E ratio, and whether it's a buy, hold, or sell. Be brief."

    print("\n🤖 Quick Analysis of Apple (AAPL)...")
    response2 = await call_perplexity(prompt2)
    print(f"\n{response2}")


async def demo_market_sentiment():
    """Demo 2: Market sentiment"""
    print("\n" + "="*60)
    print("🌍 DEMO 2: Market Sentiment Analysis")
    print("="*60)

    prompt = """What is the current market sentiment? Cover:
    - Overall market direction (bullish/bearish)
    - Key concerns investors have
    - Sectors performing well
    - Major risks ahead
    Keep it concise."""

    print("\n🤖 Analyzing market sentiment...")
    response = await call_perplexity(prompt)
    print(f"\n{response}")


async def demo_undervalued_stocks():
    """Demo 3: Find undervalued stocks"""
    print("\n" + "="*60)
    print("🔍 DEMO 3: Finding Undervalued Stocks")
    print("="*60)

    prompt = """Find me 5 undervalued stocks right now with:
    - P/E ratio under 20
    - Strong fundamentals
    - Dividend yield above 2%
    List the ticker, current price, P/E ratio, and why it's undervalued."""

    print("\n🤖 Searching for undervalued opportunities...")
    response = await call_perplexity(prompt)
    print(f"\n{response}")


async def demo_portfolio_advice():
    """Demo 4: Portfolio optimization"""
    print("\n" + "="*60)
    print("💼 DEMO 4: Portfolio Analysis")
    print("="*60)

    portfolio = ["AVGO", "MSFT", "MU", "NVDA", "TSM"]

    prompt = f"""I have positions in: {', '.join(portfolio)}

    Please analyze my portfolio:
    1. Is it well-diversified or too concentrated?
    2. Which position should I consider trimming?
    3. What sector am I missing that I should add?
    4. One specific stock to consider adding

    Be specific and actionable."""

    print(f"\n🤖 Analyzing portfolio: {', '.join(portfolio)}...")
    response = await call_perplexity(prompt)
    print(f"\n{response}")


async def demo_ai_investment_advice():
    """Demo 5: AI sector analysis"""
    print("\n" + "="*60)
    print("🤖 DEMO 5: AI Investment Opportunities")
    print("="*60)

    prompt = """Should I invest in AI stocks now or wait for a pullback?
    Consider:
    - Current valuations
    - Growth prospects
    - Recent performance
    - Specific stocks to watch (give 3)
    Give me a clear recommendation."""

    print("\n🤖 Analyzing AI investment timing...")
    response = await call_perplexity(prompt)
    print(f"\n{response}")


async def demo_earnings_analysis():
    """Demo 6: Recent earnings"""
    print("\n" + "="*60)
    print("📈 DEMO 6: Recent Earnings Analysis")
    print("="*60)

    prompt = """What were the key takeaways from recent big tech earnings?
    Focus on: NVDA, MSFT, GOOGL, META
    Include:
    - Revenue growth
    - Earnings surprises
    - Guidance changes
    - Stock price reactions"""

    print("\n🤖 Analyzing recent earnings...")
    response = await call_perplexity(prompt)
    print(f"\n{response}")


async def demo_sector_opportunities():
    """Demo 7: Sector opportunities"""
    print("\n" + "="*60)
    print("🏭 DEMO 7: Best Sectors for 2024")
    print("="*60)

    prompt = """What are the 3 best sectors to invest in for the rest of 2024?
    For each sector:
    - Why it's attractive
    - Top 2 stocks to consider
    - Key risks
    Be specific with tickers."""

    print("\n🤖 Identifying sector opportunities...")
    response = await call_perplexity(prompt)
    print(f"\n{response}")


async def demo_natural_qa():
    """Demo 8: Natural language Q&A"""
    print("\n" + "="*60)
    print("❓ DEMO 8: Natural Language Q&A")
    print("="*60)

    questions = [
        "Is the market overvalued right now?",
        "What's the best dividend stock to buy today?",
        "Should I sell my NVIDIA position after the huge run-up?"
    ]

    for q in questions:
        print(f"\n❓ Question: {q}")
        print("🤖 Researching...")
        response = await call_perplexity(q)
        print(f"\n{response}\n")
        print("-"*40)
        await asyncio.sleep(1)  # Small delay between questions


async def main():
    """Run all demos"""
    print("""
╔════════════════════════════════════════════════════════════════╗
║        🤖 PERPLEXITY AI INVESTMENT RESEARCH DEMO              ║
║                                                                ║
║  Real-time market analysis powered by advanced AI models      ║
╚════════════════════════════════════════════════════════════════╝
    """)

    # Check API key
    if not os.getenv('PERPLEXITY_API_KEY'):
        print("❌ Error: PERPLEXITY_API_KEY not set in .env file")
        return

    print(f"✅ API Key: {os.getenv('PERPLEXITY_API_KEY')[:15]}...")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("\nStarting comprehensive market analysis...\n")

    try:
        # Run demos with small delays
        await demo_stock_analysis()
        await asyncio.sleep(2)

        await demo_market_sentiment()
        await asyncio.sleep(2)

        await demo_undervalued_stocks()
        await asyncio.sleep(2)

        await demo_portfolio_advice()
        await asyncio.sleep(2)

        await demo_ai_investment_advice()
        await asyncio.sleep(2)

        await demo_earnings_analysis()
        await asyncio.sleep(2)

        await demo_sector_opportunities()
        await asyncio.sleep(2)

        await demo_natural_qa()

        print("\n" + "="*60)
        print("✅ DEMO COMPLETE!")
        print("="*60)

        print("""
💡 What This System Can Do:
════════════════════════════════════════
✓ Real-time stock analysis with current prices
✓ Market sentiment and trend analysis
✓ Find undervalued opportunities
✓ Portfolio optimization advice
✓ Sector and industry analysis
✓ Natural language Q&A about investments
✓ Earnings analysis and insights
✓ Risk assessment and recommendations

🚀 Next Steps:
1. Customize prompts for your specific needs
2. Add more sophisticated analysis
3. Integrate with trading systems
4. Set up automated monitoring
        """)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())