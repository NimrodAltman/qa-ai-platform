"""Smoke tests for the data contract and the agent registry seam."""

from qa_agents.base import BaseAgent, available_agents, get_agent
from qa_agents.models import Scenario, SqlQuery, StdResult


def test_std_result_defaults_to_empty():
    result = StdResult()
    assert result.scenarios == []
    assert result.sql_queries == []


def test_std_result_holds_scenarios_and_queries():
    result = StdResult(
        scenarios=[
            Scenario(
                entity="פרטי (contact)",
                event="שליפת אוכלוסייה - חיובי",
                target_field='שדה (new_mailreports)',
                schema="פרטי (contact)",
                condition="new_mailreports = 0 או NULL",
                expected_result="רשומה תיכלל באוכלוסייה",
            )
        ],
        sql_queries=[
            SqlQuery(
                tag="12345",
                purpose="שליפת אוכלוסייה חיובית",
                main_table="contact",
                sql="SELECT * FROM contact WHERE statecode = 0",
            )
        ],
    )
    assert len(result.scenarios) == 1
    assert len(result.sql_queries) == 1
    assert result.sql_queries[0].notes == ""


def test_registry_registers_named_agents():
    class DummyAgent(BaseAgent):
        name = "dummy"

        def run(self):
            return "ok"

    assert "dummy" in available_agents()
    assert get_agent("dummy") is DummyAgent
    assert DummyAgent().run() == "ok"
