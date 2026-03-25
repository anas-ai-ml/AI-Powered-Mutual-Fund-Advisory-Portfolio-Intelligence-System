"""
ai_agents/tasks.py
──────────────────
Orchestrates agent execution asynchronously via Celery.
Defines the main `run_pipeline` task.
"""

import logging
from celery import Celery

# Import Agent wrappers
from ai_agents.agents.market_agent import agent as market_agent
from ai_agents.agents.signal_agent import agent as signal_agent
from ai_agents.agents.prediction_agent import agent as prediction_agent
from ai_agents.agents.decision_agent import agent as decision_agent
from ai_agents.agents.fund_data_agent import agent as fund_data_agent
from ai_agents.db import storage

logger = logging.getLogger(__name__)

# Initialize Celery app, pointing configuration to celery_config.py
app = Celery("ai_agents")
app.config_from_object("ai_agents.config.celery_config")


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="ai_agents.tasks.update_fund_universe",
)
def update_fund_universe(self):
    """
    Daily task to fetch and enrich the entire mutual fund universe.
    """
    logger.info("Starting Daily Fund Universe Data Sync")
    try:
        result = fund_data_agent.run()
        logger.info(f"Fund sync complete: {result}")
        return result
    except Exception as exc:
        logger.error(f"Fund sync failed: {exc}")
        raise self.retry(exc=exc)


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="ai_agents.tasks.run_pipeline",
)
def run_pipeline(self):
    """
    The core asynchronous pipeline.
    1. Fetch market data
    2. Generate signals
    3. Predict market direction
    4. Adjust portfolio
    5. Store results
    """
    logger.info("Starting AI Agents Pipeline execution")
    try:
        market_data = market_agent.run()
        signals = signal_agent.run(market_data)
        prediction = prediction_agent.run(signals)
        decision = decision_agent.run(signals, prediction)

        storage.save(market_data, signals, prediction, decision)

        logger.info("Pipeline executed successfully")
        return {"status": "success", "agent_version": "1.0"}

    except Exception as exc:
        logger.error(f"Pipeline failed: {exc}. Retrying...")
        raise self.retry(exc=exc)
