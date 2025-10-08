#!/usr/bin/env python
"""
Working Research Demo - Demonstrates AI-powered investment research.
This version works around import issues.
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Add paths to avoid import issues
sys.path.insert(0, './autonomous')
sys.path.insert(0, './autonomous/connectors')
sys.path.insert(0, './autonomous/research')


async def demo_stock_analysis():
    """Demo: Analyze individual stocks using Perplexity"""
    print("\n" + "="*60)
    print("DEMO 1: Individual Stock Analysis with AI")
    print("="*60)

    from perplexity_finance import (
        PerplexityFinanceConnector,
        AnalysisType,
        ResearchDepth
    )

    # Initialize Perplexity connector
    perplexity = PerplexityFinanceConnector(
        api_key=os.getenv('PERPLEXITY_API_KEY')
    )

    # Analyze NVDA
    print("\n📊 Analyzing NVIDIA (NVDA) with AI...")
    analysis = await perplexity.analyze_stock(
        "NVDA",
        AnalysisType.FUNDAMENTAL,
        ResearchDepth.STANDARD
    )

    print(f"""
    🤖 AI Analysis Results:
    ════════════════════════════════════════
    Current Price: ${analysis.current_price:.2f}
    Fair Value: {f'${analysis.fair_value:.2f}' if analysis.fair_value else 'Calculating...'}
    Upside Potential: {f'{analysis.upside_potential:.1f}%' if analysis.upside_potential else 'Analyzing...'}
    P/E Ratio: {analysis.pe_ratio if analysis.pe_ratio else 'N/A'}
    Rating: {analysis.rating}
    Confidence: {analysis.confidence_score}%

    📈 Bull Case:
    {analysis.bull_case[:300]}...

    ⚠️ Key Risks:
    """ + '\n    '.join(f"• {risk}" for risk in analysis.key_risks[:3]))

    # Analyze Apple
    print("\n\n📊 Analyzing Apple (AAPL) with AI...")
    aapl_analysis = await perplexity.analyze_stock(
        "AAPL",
        AnalysisType.VALUATION,
        ResearchDepth.QUICK
    )

    print(f"""
    🤖 AI Analysis for AAPL:
    ════════════════════════════════════════
    Current Price: ${aapl_analysis.current_price:.2f}
    Rating: {aapl_analysis.rating}

    Quick Take:
    {aapl_analysis.detailed_analysis[:400]}...
    """)


async def demo_market_sentiment():
    """Demo: Analyze current market sentiment"""
    print("\n" + "="*60)
    print("DEMO 2: AI Market Sentiment Analysis")
    print("="*60)

    from perplexity_finance import PerplexityFinanceConnector

    perplexity = PerplexityFinanceConnector(
        api_key=os.getenv('PERPLEXITY_API_KEY')
    )

    # Get overall market sentiment
    print("\n🌍 Analyzing overall market sentiment with AI...")
    sentiment = await perplexity.get_market_sentiment()

    print(f"""
    🧠 AI Market Analysis:
    ════════════════════════════════════════
    {sentiment['analysis'][:600]}

    Data Freshness: {sentiment['data_freshness']}
    """)

    # Get tech sector sentiment
    print("\n💻 Analyzing technology sector...")
    tech_sentiment = await perplexity.get_market_sentiment("technology")

    print(f"""
    📱 Technology Sector Analysis:
    ════════════════════════════════════════
    {tech_sentiment['analysis'][:400]}
    """)


async def demo_stock_screening():
    """Demo: Screen for investment opportunities"""
    print("\n" + "="*60)
    print("DEMO 3: AI-Powered Stock Screening")
    print("="*60)

    from perplexity_finance import PerplexityFinanceConnector

    perplexity = PerplexityFinanceConnector(
        api_key=os.getenv('PERPLEXITY_API_KEY')
    )

    # Screen for undervalued dividend stocks
    query = "Find undervalued dividend stocks with yields above 3% and stable earnings"
    print(f"\n🔍 AI Screening Query: {query}")
    print("Searching global markets...")

    result = await perplexity.screen_stocks(query, max_results=10)

    print(f"""
    📊 AI Found {result.total_results} Matching Stocks:
    ════════════════════════════════════════""")

    for i, stock in enumerate(result.stocks[:5], 1):
        ticker = stock.get('ticker', 'N/A')
        price = stock.get('price', 0)
        print(f"""
    {i}. {ticker}
       Price: ${price:.2f if price else 'N/A'}
       {stock.get('company_name', '')}""")

    print(f"""

    📝 AI Explanation:
    {result.detailed_explanation[:400]}...
    """)


async def demo_natural_language_research():
    """Demo: Natural language investment research"""
    print("\n" + "="*60)
    print("DEMO 4: Natural Language AI Research")
    print("="*60)

    from perplexity_finance import PerplexityFinanceConnector

    perplexity = PerplexityFinanceConnector(
        api_key=os.getenv('PERPLEXITY_API_KEY')
    )

    # Ask complex investment questions
    questions = [
        "What are the most undervalued tech stocks right now with strong fundamentals?",
        "Should I invest in AI stocks or wait for a pullback?",
        "What sectors look most promising for 2024 given current market conditions?"
    ]

    for question in questions[:2]:  # Run first 2 questions
        print(f"\n❓ Question: {question}")
        print("\n🤖 AI Researching...")

        # Create a research query directly to Perplexity
        import aiohttp
        headers = {
            "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert investment analyst. Provide specific, actionable insights with tickers and numbers."
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            "max_tokens": 500,
            "temperature": 0.3
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    answer = data['choices'][0]['message']['content']

                    print(f"""
    📝 AI Answer:
    ════════════════════════════════════════
    {answer}
    """)


async def demo_portfolio_analysis():
    """Demo: Portfolio recommendations"""
    print("\n" + "="*60)
    print("DEMO 5: AI Portfolio Analysis & Recommendations")
    print("="*60)

    from perplexity_finance import PerplexityFinanceConnector

    perplexity = PerplexityFinanceConnector(
        api_key=os.getenv('PERPLEXITY_API_KEY')
    )

    # Your portfolio stocks
    portfolio = ["AVGO", "MSFT", "MU", "NVDA", "TSM"]

    print(f"\n💼 Analyzing your portfolio: {', '.join(portfolio)}")

    # Quick analysis of each position
    recommendations = []

    for ticker in portfolio[:3]:  # Analyze first 3 to avoid rate limits
        print(f"\n   Analyzing {ticker}...")
        analysis = await perplexity.analyze_stock(
            ticker,
            AnalysisType.VALUATION,
            ResearchDepth.QUICK
        )

        recommendations.append({
            'ticker': ticker,
            'rating': analysis.rating,
            'price': analysis.current_price,
            'confidence': analysis.confidence_score
        })

        await asyncio.sleep(2)  # Rate limiting

    print("\n" + "="*40)
    print("📊 AI Portfolio Recommendations:")
    print("="*40)

    for rec in recommendations:
        emoji = "🟢" if rec['rating'] == "Buy" else "🟡" if rec['rating'] == "Hold" else "🔴"
        print(f"""
    {emoji} {rec['ticker']}: {rec['rating']}
       Current: ${rec['price']:.2f}
       Confidence: {rec['confidence']}%""")

    # Get overall portfolio advice
    print("\n\n🎯 Getting AI portfolio optimization advice...")

    portfolio_question = f"""
    I have positions in {', '.join(portfolio)}.
    What changes should I consider to optimize my portfolio for growth while managing risk?
    Consider sector diversification and current market conditions.
    """

    # Query for portfolio advice
    headers = {
        "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "You are a portfolio manager. Give specific, actionable advice."},
            {"role": "user", "content": portfolio_question}
        ],
        "max_tokens": 600,
        "temperature": 0.3
    }

    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload
        ) as response:
            if response.status == 200:
                data = await response.json()
                advice = data['choices'][0]['message']['content']

                print(f"""
    💡 AI Portfolio Optimization Advice:
    ════════════════════════════════════════
    {advice}
    """)


async def demo_earnings_insider():
    """Demo: Earnings and insider trading analysis"""
    print("\n" + "="*60)
    print("DEMO 6: AI Earnings & Insider Activity Analysis")
    print("="*60)

    from perplexity_finance import PerplexityFinanceConnector

    perplexity = PerplexityFinanceConnector(
        api_key=os.getenv('PERPLEXITY_API_KEY')
    )

    # Analyze recent earnings
    print("\n📊 Analyzing recent tech earnings with AI...")

    earnings_question = """
    What were the key takeaways from the latest earnings reports of major tech companies?
    Focus on NVDA, MSFT, AAPL, and GOOGL. Include revenue growth and guidance.
    """

    import aiohttp
    headers = {
        "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "You are a financial analyst specializing in earnings analysis."},
            {"role": "user", "content": earnings_question}
        ],
        "max_tokens": 600,
        "temperature": 0.2
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload
        ) as response:
            if response.status == 200:
                data = await response.json()
                answer = data['choices'][0]['message']['content']

                print(f"""
    📈 AI Earnings Analysis:
    ════════════════════════════════════════
    {answer}
    """)


async def main():
    """Run all demos"""
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║     🤖 AI-POWERED INVESTMENT RESEARCH DEMO                ║
    ║           Powered by Perplexity Finance AI                ║
    ╚════════════════════════════════════════════════════════════╝

    This demo showcases real-time AI analysis of stocks, markets,
    and investment opportunities using cutting-edge language models.
    """)

    # Check for API key
    if not os.getenv('PERPLEXITY_API_KEY'):
        print("❌ Error: PERPLEXITY_API_KEY not set in .env file")
        return

    print(f"✅ Using API key: {os.getenv('PERPLEXITY_API_KEY')[:15]}...")
    print("\nStarting demos...\n")

    try:
        # Run all demos
        await demo_stock_analysis()
        await asyncio.sleep(2)

        await demo_market_sentiment()
        await asyncio.sleep(2)

        await demo_stock_screening()
        await asyncio.sleep(2)

        await demo_natural_language_research()
        await asyncio.sleep(2)

        await demo_portfolio_analysis()
        await asyncio.sleep(2)

        await demo_earnings_insider()

        print("\n" + "="*60)
        print("✅ ALL DEMOS COMPLETED SUCCESSFULLY!")
        print("="*60)

        print("""
    🚀 Your AI Research System Can:
    ════════════════════════════════════════
    ✓ Analyze any stock in real-time
    ✓ Answer complex investment questions
    ✓ Screen for opportunities using natural language
    ✓ Provide market sentiment analysis
    ✓ Optimize portfolio allocation
    ✓ Track earnings and insider activity
    ✓ Generate actionable recommendations

    💡 Next Steps:
    1. Run the interactive CLI for custom queries
    2. Integrate with your trading system
    3. Set up automated monitoring
    4. Customize screening criteria
        """)

    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())