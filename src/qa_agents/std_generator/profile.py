"""Output profile for the STD Generator.

A profile describes how the ``StdResult`` is laid out in the Excel workbook:
sheet names, column headers, which column each model field maps to, and
direction (RTL). Making this data — not code — is the seam that lets the same
engine serve any organization: a new org is a new profile, not new code.

``CRM_HEBREW`` is the first profile, matching the user's existing workbook.
"""

from __future__ import annotations

from dataclasses import dataclass

# A column's source: a model attribute name, the sentinel "#" for the auto row
# number, or None for a blank column the tester fills in manually.
ROW_NUMBER = "#"


@dataclass(frozen=True)
class SheetSpec:
    title: str
    columns: tuple[tuple[str, str | None], ...]  # (header, source)


@dataclass(frozen=True)
class Profile:
    name: str
    rtl: bool
    scenarios: SheetSpec
    sql: SheetSpec


CRM_HEBREW = Profile(
    name="crm-hebrew",
    rtl=True,
    scenarios=SheetSpec(
        title="תסריטים",
        columns=(
            ("מס'", ROW_NUMBER),
            ("ישות", "entity"),
            ("אירוע", "event"),
            ("שדה", "target_field"),
            ("סכמה", "schema"),
            ("תנאי/פעולה", "condition"),
            ("תוצאה צפויה", "expected_result"),
            ("תוצאת בדיקה (עבר/נכשל)", None),
            ("הערות", None),
            ("ת.הרצה", None),
            ("סבב", None),
        ),
    ),
    sql=SheetSpec(
        title="SQL",
        columns=(
            ("מס'", ROW_NUMBER),
            ("תיוג", "tag"),
            ("מטרת השאילתה", "purpose"),
            ("טבלה ראשית", "main_table"),
            ("שאילתת SQL", "sql"),
            ("הערות", "notes"),
        ),
    ),
)
