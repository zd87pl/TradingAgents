"""
Company Profile Analyst Agent
Combines Michael Burry's deep value analysis with momentum/growth analysis
"""

from langchain_core.messages import HumanMessage, SystemMessage
from tradingagents.agents.utils.prompts import ANALYST_PROMPT_TEMPLATE
from tradingagents.agents.utils.agent_states import AgentState
from langchain_core.language_models import BaseChatModel
from typing import Dict, Any


COMPANY_PROFILE_ANALYST_SYSTEM_PROMPT = """You are an expert equity analyst combining two legendary trading philosophies:

1. MICHAEL BURRY'S DEEP VALUE APPROACH:
   - Focus on intrinsic value and margin of safety
   - Analyze fundamentals: EV/EBITDA, P/E, P/B, Free Cash Flow
   - Look for contrarian opportunities (undervalued, overlooked companies)
   - Assess absolute value, not relative to peers
   - Identify "ick" stocks with hidden potential
   - Emphasize downside protection and capital preservation

2. JULIAN PETROULAS' MOMENTUM APPROACH:
   - Focus on high-conviction growth opportunities
   - Identify strong technical momentum and trends
   - Monitor market sentiment and catalysts
   - Assess competitive positioning in growth sectors
   - Look for asymmetric risk/reward setups
   - Consider shorter-term swing trading opportunities

Your task is to provide a COMPREHENSIVE COMPANY PROFILE ANALYSIS that synthesizes both approaches.

ANALYSIS FRAMEWORK:

## 1. FUNDAMENTAL VALUE ASSESSMENT (Burry Style)
Analyze:
- Valuation metrics: P/E, P/B, EV/EBITDA, PEG ratio
- Free cash flow generation and sustainability
- Balance sheet strength (debt levels, liquidity)
- Profitability metrics (margins, ROE, ROA)
- Capital allocation efficiency
- Margin of safety vs intrinsic value
- Contrarian indicators (negative sentiment, overlooked by market)

## 2. GROWTH & MOMENTUM ASSESSMENT (Petroulas Style)
Analyze:
- Revenue and earnings growth trajectory
- Market share trends and competitive positioning
- Technical momentum indicators
- Sector leadership and innovation
- Upcoming catalysts (earnings, product launches, regulatory)
- Market sentiment and positioning
- Institutional ownership and insider activity

## 3. RISK ASSESSMENT
Identify:
- Business model risks
- Competitive threats
- Regulatory risks
- Financial leverage risks
- Market sentiment risks
- Macroeconomic sensitivity

## 4. SYNTHESIZED INVESTMENT THESIS
Provide:
- Bull case (best scenario)
- Bear case (worst scenario)
- Base case (most likely)
- Key catalysts to watch
- Risk factors that could invalidate thesis
- Time horizon recommendation

## 5. OPTIONS SUITABILITY ASSESSMENT
Evaluate whether this company is suitable for call options based on:
- Volatility profile (too high = risky, too low = expensive premium)
- Catalyst timeline (upcoming events that could move stock)
- Technical setup (trending, consolidating, breaking out)
- Risk/reward asymmetry
- Liquidity in options market

OUTPUT FORMAT:
Provide a detailed markdown report with clear sections, data tables where appropriate, and specific numerical metrics.
Be objective and data-driven. Acknowledge uncertainties and conflicting signals.
End with a clear recommendation: STRONG BUY / BUY / HOLD / SELL for options call strategies.
"""


def create_company_profile_analyst(llm: BaseChatModel) -> Any:
    """
    Create company profile analyst agent

    Args:
        llm: Language model to use

    Returns:
        Compiled LangGraph agent
    """
    from tradingagents.agents.utils.tools import (
        get_stock_data,
        get_fundamentals,
        get_balance_sheet,
        get_cashflow,
        get_income_statement,
        get_indicators,
        get_news,
        get_insider_sentiment,
        get_insider_transactions,
    )

    tools = [
        get_stock_data,
        get_fundamentals,
        get_balance_sheet,
        get_cashflow,
        get_income_statement,
        get_indicators,
        get_news,
        get_insider_sentiment,
        get_insider_transactions,
    ]

    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: AgentState):
        """Agent node that processes company analysis"""
        messages = [
            SystemMessage(content=COMPANY_PROFILE_ANALYST_SYSTEM_PROMPT),
            HumanMessage(
                content=f"""Analyze {state['company_of_interest']} as of {state['trade_date']}.

Provide a comprehensive company profile analysis combining Michael Burry's value investing principles
and momentum/growth analysis suitable for options call strategies.

Use all available tools to gather:
1. Historical stock price and technical indicators
2. Fundamental financials (balance sheet, income statement, cash flow)
3. Recent news and market sentiment
4. Insider transactions and sentiment

Then synthesize this information into a detailed investment thesis suitable for options trading decisions.
"""
            )
        ]

        # Add existing messages
        messages.extend(state.get("messages", []))

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    # Create the graph
    from langgraph.prebuilt import create_react_agent

    agent = create_react_agent(llm, tools, state_schema=AgentState)

    return agent


def analyze_company_profile(
    ticker: str,
    trade_date: str,
    llm: BaseChatModel,
    state: AgentState = None
) -> str:
    """
    Standalone function to analyze company profile

    Args:
        ticker: Stock ticker symbol
        trade_date: Analysis date
        llm: Language model
        state: Optional existing state

    Returns:
        Company profile analysis report
    """
    if state is None:
        state = {
            "company_of_interest": ticker,
            "trade_date": trade_date,
            "messages": []
        }

    agent = create_company_profile_analyst(llm)

    # Run the agent
    result = agent.invoke(state)

    # Extract the analysis from messages
    messages = result.get("messages", [])
    if messages:
        # Get the last AI message
        for msg in reversed(messages):
            if hasattr(msg, 'content') and isinstance(msg.content, str):
                if len(msg.content) > 100:  # Actual analysis, not tool calls
                    return msg.content

    return "Unable to generate company profile analysis"
