"""Prompt construction for the STD Generator.

The prompt text is written for the CRM_HEBREW profile. When multi-profile
support lands, the persona and domain rules move into the profile itself; for
now they live here so the first agent works end to end.
"""

from __future__ import annotations

from .profile import Profile

_SYSTEM = """\
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


def build_system_prompt(profile: Profile) -> str:
    """Return the system prompt for the given profile."""
    # profile is accepted so future profiles can vary persona/language/rules;
    # CRM_HEBREW uses the default text above.
    return _SYSTEM


def build_user_prompt(
    spec_text: str,
    tag: str | None = None,
    scenarios: bool = True,
    sql: bool = True,
) -> str:
    """Return the user prompt for the specification.

    ``tag`` selects a specific task tag; ``None`` means cover the whole spec.
    ``scenarios`` / ``sql`` select which outputs to produce.
    """
    if tag:
        scope = f'תיוג משימה: {tag}\nהפק עבור התיוג הנ"ל בלבד.'
    else:
        scope = "מצב הרצה: כלל האפיון. הפק עבור כל התיוגים/התהליכים שמופיעים באפיון."

    if scenarios and sql:
        outputs = "הפק תסריטי בדיקה ושאילתות SQL."
    elif scenarios:
        outputs = "הפק תסריטי בדיקה בלבד. החזר את מערך sql_queries ריק."
    else:
        outputs = "הפק שאילתות SQL בלבד. החזר את מערך scenarios ריק."

    return (
        f"{scope}\n{outputs}\n\n"
        f"--- אפיון ---\n{spec_text}"
    )
