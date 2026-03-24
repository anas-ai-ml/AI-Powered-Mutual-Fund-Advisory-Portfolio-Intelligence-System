"""
Tests for ai_agents architecture.
Validates the wrapper classes and FastAPI endpoint logic.
"""
import pytest
from fastapi.testclient import TestClient

from ai_agents.agents.market_agent import agent as market_agent
from ai_agents.agents.signal_agent import agent as signal_agent
from ai_agents.agents.prediction_agent import agent as prediction_agent
from ai_agents.agents.decision_agent import agent as decision_agent
from ai_agents.api import app

client = TestClient(app)

class TestAgentsArchitecture:
    
    def test_market_agent_returns_structured_data(self, mocker):
        # Mock ai_layer
        mocker.patch("ai_agents.agents.market_agent.get_market_snapshot", return_value={"nifty_price": 22000})
        mocker.patch("ai_agents.agents.market_agent.get_macro_indicators", return_value={"cpi": 6.0})
        
        result = market_agent.run()
        assert "market_snapshot" in result
        assert "macro_indicators" in result
        assert result["agent_version"] == "1.0"

    def test_signal_agent_extracts_from_market_wrapper(self, mocker):
        mocker.patch("ai_agents.agents.signal_agent.generate_signals", return_value={"trend": "bullish"})
        
        fake_market = {"market_snapshot": {}, "macro_indicators": {}}
        result = signal_agent.run(fake_market)
        
        assert result["trend"] == "bullish"
        assert result["agent_version"] == "1.0"

    def test_prediction_agent_probabilistic_boundaries(self):
        signals_bullish_low_vol = {
            "market_trend": "bullish",
            "volatility": "low",
            "global_sentiment": "positive",
            "inflation_trend": "stable",
            "repo_rate_pct": 6.5,
        }
        
        result = prediction_agent.run(signals_bullish_low_vol)
        assert result["direction"] == "up"             # High confidence
        assert result["confidence"] > 0.70             # Starts at .60, adds modifiers
        assert result["expected_return"]["low_pct"] == 7.5 # repo + 1
        assert result["expected_return"]["mid_pct"] > 14.0 # 20.0 * 0.75+
        assert result["expected_return"]["high_pct"] > result["expected_return"]["mid_pct"]

    def test_decision_agent_returns_adjustments(self, mocker):
        mock_adaptive = {
            "adaptive_allocation": {"Equity": 45, "Debt": 40},
            "equity_delta": -5,
            "debt_delta": 5,
        }
        mocker.patch("ai_agents.agents.decision_agent.apply_adaptive_allocation", return_value=mock_adaptive)
        
        result = decision_agent.run({}, {})
        assert "adaptive_allocation" in result
        assert result["adjustments"]["equity_delta"] == -5

class TestApiEndpoints:
    
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()
        
    def test_live_advice_pending(self, mocker):
        # Mock storage to return None
        mocker.patch("ai_agents.api.storage.get_latest", return_value=None)
        mocker.patch("ai_agents.api.run_pipeline.delay")
        
        response = client.get("/live-advice")
        assert response.status_code == 202
        assert response.json()["status"] == "pending"

    def test_run_pipeline_triggers_task(self, mocker):
        mock_task = mocker.patch("ai_agents.api.run_pipeline.delay")
        mock_task.return_value.id = "mock-task-id-123"
        
        response = client.post("/run-pipeline")
        assert response.status_code == 200
        assert response.json()["task_id"] == "mock-task-id-123"
