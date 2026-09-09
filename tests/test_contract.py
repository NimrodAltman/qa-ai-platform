"""Smoke tests for the data contract and the agent registry seam."""

from qa_agents.base import BaseAgent, available_agents, get_agent, list_agents
from qa_agents.models import Scenario, SqlQuery, StdResult
from qa_agents.spec_analyzer.agent import SpecAnalyzerAgent
from qa_agents.std_generator.agent import StdGeneratorAgent


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
                target_field='שדה (demo_mailoptout)',
                schema="פרטי (contact)",
                condition="demo_mailoptout = 0 או NULL",
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


def test_list_agents_exposes_catalog_metadata_for_real_agents():
    catalog = {entry["name"]: entry for entry in list_agents()}
    for cls in (StdGeneratorAgent, SpecAnalyzerAgent):
        entry = catalog[cls.name]
        assert entry["display_name"] == cls.display_name
        assert entry["description"] == cls.description
        assert entry["output_format"] == cls.output_format
        assert entry["display_name"] and entry["description"] and entry["output_format"]
