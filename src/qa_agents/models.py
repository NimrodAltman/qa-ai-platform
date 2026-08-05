"""Data contract shared across QA agents.

The STD Generator agent produces an ``StdResult`` — a structured representation
of what the agent extracted from a specification. The Excel engine turns this
structure into the workbook; the agent never writes the file itself.

Field names mirror the columns the agent fills in the source workbook:

    תסריטים: ישות | אירוע | שדה | סכמה | תנאי/פעולה | תוצאה צפויה
    SQL:     תיוג | מטרת השאילתה | טבלה ראשית | שאילתת SQL | הערות

The scenario's manual columns (תוצאת בדיקה, הערות, ת.הרצה, סבב) and the row
number (מס') are added by the Excel engine, not by the agent, so they are not
part of this contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Scenario:
    """One row in the תסריטים sheet — the six columns the agent fills."""

    entity: str            # ישות
    event: str             # אירוע
    target_field: str      # שדה
    schema: str            # סכמה
    condition: str         # תנאי/פעולה
    expected_result: str   # תוצאה צפויה


@dataclass
class SqlQuery:
    """One row in the SQL sheet."""

    tag: str               # תיוג
    purpose: str           # מטרת השאילתה
    main_table: str        # טבלה ראשית
    sql: str               # שאילתת SQL
    notes: str = ""        # הערות


@dataclass
class StdResult:
    """The full output of the STD Generator for a single request."""

    scenarios: list[Scenario] = field(default_factory=list)
    sql_queries: list[SqlQuery] = field(default_factory=list)
