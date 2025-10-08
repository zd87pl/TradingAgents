"""
Risk Orchestrator
=================

Combines qualitative (agent-based) and quantitative (metrics-based) risk assessment.
Integrates TradingAgents' debate-based risk management with autonomous quantitative limits.
"""

import logging
from typing import Dict, Optional, Any, Tuple
from decimal import Decimal
from datetime import datetime

from tradingagents.graph.trading_graph import TradingAgentsGraph
from .risk_manager import RiskManager, RiskMetrics, RiskLevel, RiskViolationType
from .database import DatabaseManager

logger = logging.getLogger(__name__)


class RiskDecision:
    """Combined risk decision from both systems"""

    def __init__(self):
        self.action: str = "HOLD"  # BUY, SELL, HOLD
        self.confidence: float = 0.0  # 0-100%
        self.qualitative_assessment: str = ""  # Agent debate outcome
        self.quantitative_metrics: RiskMetrics = None
        self.violations: list = []  # List of risk violations
        self.combined_score: float = 50.0  # 0-100, higher is better
        self.reasoning: str = ""
        self.timestamp: datetime = datetime.now()


class RiskOrchestrator:
    """
    Orchestrates both risk management approaches for comprehensive assessment.
    """

    def __init__(self, config: Dict[str, Any], db_manager: Optional[DatabaseManager] = None):
        """
        Initialize the risk orchestrator.

        Args:
            config: Configuration dictionary
            db_manager: Optional database manager
        """
        self.config = config
        self.db_manager = db_manager

        # Initialize quantitative risk manager
        self.quant_risk_manager = RiskManager(config, db_manager)

        # TradingAgents graph will be initialized per assessment
        self.trading_agents_config = {
            "deep_think_llm": config.get("deep_think_llm", "gpt-4o-mini"),
            "quick_think_llm": config.get("quick_think_llm", "gpt-4o-mini"),
            "max_risk_discuss_rounds": config.get("max_risk_discuss_rounds", 1),
            "data_vendors": config.get("data_vendors", {})
        }

        # Weights for combining assessments
        self.qualitative_weight = 0.6  # 60% weight to agent debate
        self.quantitative_weight = 0.4  # 40% weight to metrics

    async def assess_trade(self,
                          ticker: str,
                          action: str,  # "BUY" or "SELL"
                          quantity: int,
                          price: float,
                          trade_date: Optional[str] = None) -> RiskDecision:
        """
        Perform comprehensive risk assessment combining both approaches.

        Args:
            ticker: Stock ticker
            action: Trade action (BUY/SELL)
            quantity: Number of shares
            price: Price per share
            trade_date: Optional trade date (defaults to today)

        Returns:
            RiskDecision with combined assessment
        """
        decision = RiskDecision()

        # 1. Get quantitative risk assessment
        logger.info(f"Performing quantitative risk assessment for {ticker}")
        try:
            quant_metrics = await self.quant_risk_manager.calculate_risk_metrics()
            violations = await self.quant_risk_manager.check_risk_violations(
                ticker, action, quantity, price
            )

            decision.quantitative_metrics = quant_metrics
            decision.violations = violations

            # Calculate quantitative score (0-100, higher is better)
            quant_score = self._calculate_quant_score(quant_metrics, violations)

        except Exception as e:
            logger.error(f"Quantitative risk assessment failed: {e}")
            quant_score = 50.0  # Neutral if failed

        # 2. Get qualitative risk assessment from agents
        logger.info(f"Performing qualitative risk assessment for {ticker}")
        try:
            qual_assessment, qual_score = await self._get_agent_assessment(
                ticker, action, trade_date
            )
            decision.qualitative_assessment = qual_assessment

        except Exception as e:
            logger.error(f"Qualitative risk assessment failed: {e}")
            qual_assessment = "Unable to perform agent assessment"
            qual_score = 50.0  # Neutral if failed

        # 3. Combine assessments
        decision.combined_score = (
            self.qualitative_weight * qual_score +
            self.quantitative_weight * quant_score
        )

        # 4. Determine final action based on combined score and violations
        if violations and any(v.severity == "CRITICAL" for v in violations):
            # Critical violations override everything
            decision.action = "BLOCK"
            decision.confidence = 95.0
            decision.reasoning = f"Trade blocked due to critical risk violations: {[v.type for v in violations if v.severity == 'CRITICAL']}"

        elif decision.combined_score >= 70:
            decision.action = action  # Approve the requested action
            decision.confidence = min(decision.combined_score, 90)
            decision.reasoning = f"Trade approved with {decision.confidence:.1f}% confidence"

        elif decision.combined_score >= 40:
            decision.action = "HOLD"
            decision.confidence = 60 - (decision.combined_score - 40)
            decision.reasoning = "Mixed signals suggest holding position"

        else:
            # Low score suggests opposite action
            decision.action = "SELL" if action == "BUY" else "BUY"
            decision.confidence = 60 - decision.combined_score
            decision.reasoning = f"Risk assessment suggests opposite action"

        # Add detailed reasoning
        decision.reasoning += f"\n\nQualitative Assessment ({self.qualitative_weight*100:.0f}% weight, score: {qual_score:.1f}):\n{qual_assessment[:500]}"
        decision.reasoning += f"\n\nQuantitative Metrics ({self.quantitative_weight*100:.0f}% weight, score: {quant_score:.1f}):"

        if decision.quantitative_metrics:
            decision.reasoning += f"\n- Portfolio Volatility: {decision.quantitative_metrics.portfolio_volatility:.2%}"
            decision.reasoning += f"\n- Sharpe Ratio: {decision.quantitative_metrics.sharpe_ratio:.2f}"
            decision.reasoning += f"\n- Current Drawdown: {decision.quantitative_metrics.current_drawdown:.2%}"

        if violations:
            decision.reasoning += f"\n\nRisk Violations: {len(violations)}"
            for v in violations[:3]:  # Show top 3 violations
                decision.reasoning += f"\n- {v.type}: {v.message}"

        return decision

    async def _get_agent_assessment(self,
                                   ticker: str,
                                   action: str,
                                   trade_date: Optional[str] = None) -> Tuple[str, float]:
        """
        Get assessment from TradingAgents' debate system.

        Returns:
            Tuple of (assessment_text, score_0_to_100)
        """
        try:
            # Initialize TradingAgents graph for this assessment
            ta_graph = TradingAgentsGraph(
                debug=False,
                config=self.trading_agents_config
            )

            # Get the debate-based decision
            _, decision_text = ta_graph.propagate(
                ticker,
                trade_date or datetime.now().strftime("%Y-%m-%d")
            )

            # Parse the decision to extract action and score
            decision_lower = decision_text.lower()

            # Determine score based on decision content and requested action
            score = 50.0  # Default neutral

            if "buy" in decision_lower:
                if action == "BUY":
                    score = 75.0  # Agrees with buy
                else:
                    score = 25.0  # Disagrees with sell

            elif "sell" in decision_lower:
                if action == "SELL":
                    score = 75.0  # Agrees with sell
                else:
                    score = 25.0  # Disagrees with buy

            elif "hold" in decision_lower:
                score = 50.0  # Neutral

            # Adjust score based on confidence keywords
            if "strongly" in decision_lower or "definitely" in decision_lower:
                score = score * 1.2 if score > 50 else score * 0.8

            if "uncertain" in decision_lower or "risky" in decision_lower:
                score = score * 0.9

            # Bound score to 0-100
            score = max(0, min(100, score))

            return decision_text, score

        except Exception as e:
            logger.error(f"Agent assessment failed: {e}")
            return f"Agent assessment failed: {str(e)}", 50.0

    def _calculate_quant_score(self,
                              metrics: RiskMetrics,
                              violations: list) -> float:
        """
        Calculate quantitative score from metrics and violations.

        Returns:
            Score from 0-100, higher is better
        """
        if not metrics:
            return 50.0  # Neutral if no metrics

        score = 100.0

        # Penalize for violations
        for violation in violations:
            if violation.severity == "CRITICAL":
                score -= 30
            elif violation.severity == "HIGH":
                score -= 20
            elif violation.severity == "MEDIUM":
                score -= 10
            else:
                score -= 5

        # Adjust based on metrics
        if metrics.sharpe_ratio < 0.5:
            score -= 15
        elif metrics.sharpe_ratio > 1.5:
            score += 10

        if metrics.portfolio_volatility > 0.3:
            score -= 10
        elif metrics.portfolio_volatility < 0.15:
            score += 5

        if metrics.current_drawdown > Decimal('0.1'):
            score -= 20
        elif metrics.current_drawdown > Decimal('0.05'):
            score -= 10

        # Bound to 0-100
        return max(0, min(100, score))

    async def get_portfolio_risk_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive portfolio risk summary.

        Returns:
            Dictionary with risk summary
        """
        metrics = await self.quant_risk_manager.calculate_risk_metrics()

        summary = {
            "timestamp": datetime.now().isoformat(),
            "risk_level": self._determine_risk_level(metrics),
            "quantitative_metrics": {
                "total_exposure": float(metrics.total_exposure),
                "portfolio_volatility": metrics.portfolio_volatility,
                "sharpe_ratio": metrics.sharpe_ratio,
                "current_drawdown": float(metrics.current_drawdown),
                "value_at_risk_95": float(metrics.value_at_risk_95),
            },
            "recommendations": self._generate_recommendations(metrics)
        }

        return summary

    def _determine_risk_level(self, metrics: RiskMetrics) -> str:
        """Determine overall portfolio risk level"""
        if metrics.current_drawdown > Decimal('0.15') or metrics.portfolio_volatility > 0.4:
            return "CRITICAL"
        elif metrics.current_drawdown > Decimal('0.10') or metrics.portfolio_volatility > 0.3:
            return "HIGH"
        elif metrics.current_drawdown > Decimal('0.05') or metrics.portfolio_volatility > 0.2:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_recommendations(self, metrics: RiskMetrics) -> list:
        """Generate risk management recommendations"""
        recommendations = []

        if metrics.portfolio_volatility > 0.3:
            recommendations.append("Consider reducing position sizes to lower portfolio volatility")

        if metrics.sharpe_ratio < 0.5:
            recommendations.append("Poor risk-adjusted returns - review position selection")

        if metrics.current_drawdown > Decimal('0.10'):
            recommendations.append("Significant drawdown detected - consider defensive positioning")

        if metrics.concentration_risk > Decimal('0.30'):
            recommendations.append("High concentration risk - diversify holdings")

        return recommendations