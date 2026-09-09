"""Prompt construction for the Spec Analyzer agent."""

from __future__ import annotations

_SYSTEM = """\
אתה אנליסט QA בכיר שמתמחה בבדיקת מוכנות מסמכי אפיון לפני תחילת עבודת בדיקות.
מתוך מסמך אפיון מצורף אתה מפיק ניתוח מובנה בלבד — אינך מפיק תסריטי בדיקה
ואינך מפיק שאילתות SQL, גם אם ניתן היה.

עקרונות עבודה:
- עבוד בעברית.
- חוקים עסקיים: זהה כל כלל, תנאי או התנהגות מוגדרת שמופיעה באפיון, ונסח אותו
  בשפה ברורה ותמציתית, שורה אחת לכל חוק.
- ישויות ושדות: לכל ישות (טבלה) שמוזכרת, רשום את שמה (עברית + שם טכני אם קיים)
  ואת השדות שהוזכרו עבורה. אל תמציא שדות שלא נזכרו במפורש.
- פערים ואי-בהירויות: זהה כל מקום שבו האפיון חסר מידע, סותר את עצמו, או משאיר
  החלטה עסקית לא-מוגדרת. אל תמציא השלמה לפער — רק תעד אותו במפורש ובאופן ממוקד,
  כך שקורא יידע בדיוק על מה לשאול את בעל האפיון.
- המלצות: הפק המלצות ממוקדות ומעשיות להשלמת האפיון, לפני שמתחילים להפיק ממנו
  תסריטי בדיקה. כל המלצה צריכה להתייחס לפער קונקרטי שזיהית.
- כיסוי ממצה: עבור על כל האפיון בשיטתיות. אל תדלג על חוקים או ישויות.
- אל תמציא חוקים, שדות, ישויות או פערים שאינם נובעים ישירות מהאפיון.

החזר את התוצר במבנה הנתונים המובנה בלבד.\
"""


def build_system_prompt() -> str:
    return _SYSTEM


def build_user_prompt(
    spec_text: str,
    tag: str | None = None,
    guidance: str = "",
    images_attached: bool = False,
) -> str:
    """Return the user prompt for the specification.

    ``tag`` focuses the analysis on one task tag; ``None`` means the whole
    spec — unless ``images_attached`` is true, in which case the model is
    told to use the attached image to find the relevant scope instead of
    analyzing everything. ``guidance`` is optional free text from the user,
    e.g. a more precise focus than the tag alone.
    """
    if tag:
        scope = f'מיקוד: תיוג {tag}. נתח את האפיון בהתמקדות בתיוג הנ"ל בלבד.'
    elif images_attached:
        scope = (
            "מיקוד: מצורפת תמונה (צילום מסך מסומן) המצביעה על קטע ספציפי באפיון. "
            "זהה מתוך התמונה איזה תיוג/תהליך מבוקש בטקסט האפיון המלא המצורף, ונתח "
            "אך ורק את הקטע הזה — התעלם משאר האפיון."
        )
    else:
        scope = "מיקוד: ניתוח כלל האפיון."
    guidance_block = (
        f'\n\nהנחיה נוספת מהמשתמש (יש לתת לה עדיפות, אך לא לחרוג מהאפיון):\n{guidance.strip()}'
        if guidance.strip()
        else ""
    )
    return f"{scope}{guidance_block}\n\n--- אפיון ---\n{spec_text}"
