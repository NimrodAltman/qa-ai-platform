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
- כיסוי חובה כאשר רלוונטי: חיובי (רשומות שנכללות/מתעדכנות), שלילי (שלא), וקצה
  (NULL, ריק, אפסים מובילים, סטטוס לא תקין, תאריכים חריגים, כפילויות).
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


def build_user_prompt(spec_text: str, tag: str) -> str:
    """Return the user prompt carrying the specification and the task tag."""
    return (
        f"תיוג משימה: {tag}\n\n"
        f"להלן תוכן האפיון. הפק תסריטי בדיקה ושאילתות SQL עבור התיוג הנ\"ל בלבד.\n\n"
        f"--- אפיון ---\n{spec_text}"
    )
