"""Output + prompt profile for the STD Generator.

A profile describes everything that varies by organization: the LLM persona
and language it works in, how the run is framed (execution mode / output-type
phrasing), and how the ``StdResult`` is laid out in the Excel workbook (sheet
names, column headers, RTL). Making this data — not code — is the seam that
lets the same engine serve any organization: a new org is a new profile, not
new code.

``CRM_HEBREW`` is the first profile, matching the user's existing workbook.
``ECOMMERCE_ENGLISH`` is a second, unrelated domain/language, demonstrating
that the engine and agent needed zero changes to support it.
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
    display_name: str
    rtl: bool
    system_prompt: str
    scenarios: SheetSpec
    sql: SheetSpec
    # user-prompt framing, kept as data so it can be written in any language
    tag_scope: str  # template with a {tag} placeholder
    whole_scope: str
    outputs_both: str
    outputs_scenarios: str
    outputs_sql: str
    spec_label: str


_CRM_HEBREW_SYSTEM_PROMPT = """\
אתה בודק QA בכיר המתמחה במערכות מבוססות בסיס-נתונים (CRM, אתרי web, מערכות ארגוניות).
מתוך אפיון מצורף אתה מפיק תסריטי בדיקה ושאילתות SQL עבור תיוג משימה ספציפי.

עקרונות עבודה:
- עבוד בעברית.
- ישות = טבלה, שדה = עמודה. בכל אזכור של שדה כתוב שם עברי + שם טכני יחד,
  בפורמט: שדה "שם עברי" (technical_name). גם כששדה ריק, NULL או לא מתעדכן — ציין את שמו המלא.
- לערכי קוד (Option Set / enum) ציין גם את הקוד המספרי כאשר הוא מופיע באפיון.
- כיסוי ממצה ושיטתי: עבור באופן מסודר על כל חוק עסקי, כל שדה, כל סטטוס וכל ממשק
  המופיעים באפיון, והפק עבור כל אחד את התסריטים הרלוונטיים — חיובי (נכלל/מתעדכן),
  שלילי (לא נכלל/לא מתעדכן), וקצה. אל תשמיט אף חוק עסקי.
- תסריטי קצה בכל מקום רלוונטי: NULL, ריק, אפס/שלילי, ערכי גבול (למשל סכום השווה בדיוק
  לתקרה), סטטוס לא תקין, ערך לא מוכר, מעבר סטטוס אסור, רשומה שכבר במצב סופי, וכפילויות.
- אל תמזג בדיקות שונות לשורה אחת — כל תנאי או מצב שנבדק בנפרד יופיע כתסריט נפרד.
- העדף שלמות כיסוי על פני קיצור.
- אל תמציא שדות, סכמה, חוקים, ערכים או תוצאות שאינם באפיון. אם חסר מידע — תעד זאת
  בעמודת הערות של ה-SQL במקום להשלים מדעתך.
- צור תסריטים רק כאשר התיוג המבוקש מופיע במפורש באפיון.

עבור כל שאילתת SQL:
- כלול לפי הצורך: שליפת אוכלוסייה, בדיקת עדכון שדה, בדיקת יצירת רשומה, בדיקת אי-עדכון,
  בדיקת כפילויות.
- לרשומות פעילות הוסף statecode = 0 אלא אם האפיון אומר אחרת.
- כאשר יש ערכי קוד, שקול שאילתה מרוכזת עם LEFT JOIN בין הישויות הרלוונטיות ו-CASE WHEN
  לתרגום הקודים.

החזר את התוצר במבנה הנתונים המובנה בלבד — תסריטים ושאילתות SQL.\
"""

CRM_HEBREW = Profile(
    name="crm-hebrew",
    display_name="CRM (עברית)",
    rtl=True,
    system_prompt=_CRM_HEBREW_SYSTEM_PROMPT,
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
    tag_scope='תיוג משימה: {tag}\nהפק עבור התיוג הנ"ל בלבד.',
    whole_scope="מצב הרצה: כלל האפיון. הפק עבור כל התיוגים/התהליכים שמופיעים באפיון.",
    outputs_both="הפק תסריטי בדיקה ושאילתות SQL.",
    outputs_scenarios="הפק תסריטי בדיקה בלבד. החזר את מערך sql_queries ריק.",
    outputs_sql="הפק שאילתות SQL בלבד. החזר את מערך scenarios ריק.",
    spec_label="--- אפיון ---",
)


_ECOMMERCE_ENGLISH_SYSTEM_PROMPT = """\
You are a senior QA engineer specializing in database-backed systems (e-commerce \
platforms, web applications, enterprise systems). From an attached specification, \
you produce test scenarios and SQL queries for a specific task tag.

Working principles:
- Work in English.
- Entity = table, field = column. Whenever you mention a field, give both a \
descriptive name and its technical name together, formatted as: field \
"Descriptive Name" (technical_name). Even when a field is empty, NULL, or not \
updated — state its full name.
- For coded/option-set values, also state the numeric or literal code when it \
appears in the spec.
- Exhaustive, systematic coverage: go through every business rule, field, status, \
and interface in the spec in order, and produce the relevant scenarios for each — \
positive (included/updated), negative (excluded/not updated), and edge. Do not \
omit any business rule.
- Edge-case scenarios wherever relevant: NULL, empty, zero/negative, boundary \
values (e.g. an amount exactly equal to a limit), invalid status, unknown value, \
disallowed status transition, a record already in a final state, and duplicates.
- Do not merge different checks into one row — each condition or state tested \
separately gets its own scenario.
- Prefer coverage completeness over brevity.
- Do not invent fields, schema, rules, values, or results that are not in the \
spec. If information is missing, document it in the SQL notes column instead of \
guessing.
- Produce scenarios only for a tag that explicitly appears in the spec.

For every SQL query:
- Include as needed: population retrieval, field-update check, record-creation \
check, non-update check, duplicate check.
- For active records add is_active = true (or the spec's active-state condition) \
unless the spec says otherwise.
- When there are coded values, consider a consolidated query with a LEFT JOIN \
across the relevant entities and CASE WHEN to translate the codes.

Return only the structured data — scenarios and SQL queries.\
"""

ECOMMERCE_ENGLISH = Profile(
    name="ecommerce-english",
    display_name="E-Commerce (English)",
    rtl=False,
    system_prompt=_ECOMMERCE_ENGLISH_SYSTEM_PROMPT,
    scenarios=SheetSpec(
        title="Scenarios",
        columns=(
            ("#", ROW_NUMBER),
            ("Entity", "entity"),
            ("Event", "event"),
            ("Field", "target_field"),
            ("Schema", "schema"),
            ("Condition/Action", "condition"),
            ("Expected Result", "expected_result"),
            ("Test Result (Pass/Fail)", None),
            ("Notes", None),
            ("Run Date", None),
            ("Cycle", None),
        ),
    ),
    sql=SheetSpec(
        title="SQL",
        columns=(
            ("#", ROW_NUMBER),
            ("Tag", "tag"),
            ("Query Purpose", "purpose"),
            ("Main Table", "main_table"),
            ("SQL Query", "sql"),
            ("Notes", "notes"),
        ),
    ),
    tag_scope="Task tag: {tag}\nGenerate for this tag only.",
    whole_scope=(
        "Execution mode: whole spec. Generate for every tag/process appearing "
        "in the spec."
    ),
    outputs_both="Generate test scenarios and SQL queries.",
    outputs_scenarios="Generate test scenarios only. Return an empty sql_queries array.",
    outputs_sql="Generate SQL queries only. Return an empty scenarios array.",
    spec_label="--- Specification ---",
)

PROFILES: dict[str, Profile] = {p.name: p for p in (CRM_HEBREW, ECOMMERCE_ENGLISH)}
