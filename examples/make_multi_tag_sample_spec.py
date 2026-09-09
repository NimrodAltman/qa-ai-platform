"""Generate a large, fully fictional multi-process specification.

Run:  python examples/make_multi_tag_sample_spec.py

15 short, unrelated business processes, each under its own task tag and with
its own distinct entity/fields — built specifically to test tag-scoping:
pick one tag and confirm the agent's output only reflects that section, not
leaked content from the other 14. Invented data, no real organization.
"""

from pathlib import Path

import docx

# Each: (tag, title, entity_hebrew, entity_tech, [(field_he, field_tech, note)], [rules])
SECTIONS = [
    (
        "50001", "אישור בקשת החזר כספי", "בקשת החזר", "req_refund",
        [
            ("סטטוס בקשה", "req_status", "קוד: 1=חדשה, 2=אושרה, 3=נדחתה"),
            ("סכום מבוקש", "req_amount", "מספרי, חייב להיות גדול מ-0"),
        ],
        [
            "בקשה מאושרת רק אם req_status = 1 והסכום המבוקש קטן או שווה ל-5000.",
            "בקשה עם סכום מעל 5000 נדחית אוטומטית (req_status = 3).",
        ],
    ),
    (
        "50002", "אישור הרשמת לקוח חדש", "הרשמה", "reg_signup",
        [
            ("סטטוס הרשמה", "reg_status", "קוד: 1=ממתין, 2=אושר, 3=נדחה"),
            ("אימות אימייל", "reg_emailverified", "בוליאני"),
        ],
        [
            "הרשמה מאושרת רק אם reg_emailverified = true.",
            "הרשמה ללא אימות אימייל תוך 7 ימים נדחית אוטומטית.",
        ],
    ),
    (
        "50003", "בקשת איפוס סיסמה", "בקשת איפוס", "pwd_reset",
        [
            ("סטטוס בקשה", "pwd_status", "קוד: 1=נשלח, 2=נוצל, 3=פג תוקף"),
            ("תוקף (דקות)", "pwd_expiry", "מספרי, ברירת מחדל 30"),
        ],
        [
            "קישור איפוס תקף רק תוך pwd_expiry דקות מהיצירה.",
            "לא ניתן לנצל קישור שכבר סומן כ-pwd_status = 2 (נוצל).",
        ],
    ),
    (
        "50004", "ביטול מנוי", "מנוי", "sub_subscription",
        [
            ("סטטוס מנוי", "sub_status", "קוד: 1=פעיל, 2=מבוטל, 3=מושהה"),
            ("סיבת ביטול", "sub_cancelreason", "טקסט חופשי"),
        ],
        [
            "ביטול מנוי מעדכן sub_status = 2 ומחייב סיבת ביטול (sub_cancelreason לא ריק).",
            "מנוי מושהה (3) לא ניתן לביטול ישיר — יש לשחזר לפעיל תחילה.",
        ],
    ),
    (
        "50005", "מימוש קוד הנחה", "קוד הנחה", "cpn_coupon",
        [
            ("סטטוס קוד", "cpn_status", "קוד: 1=פעיל, 2=נוצל, 3=פג תוקף"),
            ("מספר שימושים", "cpn_usagecount", "מספרי"),
            ("מגבלת שימושים", "cpn_usagelimit", "מספרי"),
        ],
        [
            "קוד ניתן למימוש רק אם cpn_status = 1 ו-cpn_usagecount קטן מ-cpn_usagelimit.",
            "בכל מימוש מוצלח, cpn_usagecount גדל ב-1.",
        ],
    ),
    (
        "50006", "עדכון מעקב משלוח הזמנה", "משלוח", "shp_shipment",
        [
            ("סטטוס משלוח", "shp_status", "קוד: 1=נשלח, 2=בדרך, 3=נמסר, 4=עוכב"),
            ("חברת שילוח", "shp_carrier", "טקסט"),
        ],
        [
            "מעבר לסטטוס נמסר (3) מתאפשר רק מסטטוס בדרך (2).",
            "משלוח מעוכב (4) חייב הערה מפורטת בשדה הערות ה-SQL.",
        ],
    ),
    (
        "50007", "בקרת ביקורות מוצר", "ביקורת", "rev_review",
        [
            ("סטטוס ביקורת", "rev_status", "קוד: 1=ממתין, 2=פורסם, 3=נדחה"),
            ("סיבת סימון", "rev_flagreason", "טקסט, מתמלא רק כשנדחה"),
        ],
        [
            "ביקורת עם דירוג 1 כוכב מסומנת אוטומטית לבדיקה ידנית לפני פרסום.",
            "ביקורת שנדחתה (3) חייבת rev_flagreason מלא.",
        ],
    ),
    (
        "50008", "מימוש נקודות נאמנות", "עסקת נקודות", "pts_transaction",
        [
            ("סטטוס עסקה", "pts_status", "קוד: 1=בוצע, 2=בוטל"),
            ("כמות נקודות", "pts_amount", "מספרי, חייב להיות גדול מ-0"),
        ],
        [
            "מימוש נקודות מתאפשר רק אם ליתרת הלקוח יש מספיק נקודות פנויות.",
            "עסקה שבוטלה (2) מחזירה את הנקודות ליתרת הלקוח.",
        ],
    ),
    (
        "50009", "הסלמת קריאת שירות", "קריאת שירות", "tkt_ticket",
        [
            ("עדיפות", "tkt_priority", "קוד: 1=נמוכה, 2=בינונית, 3=גבוהה"),
            ("הוסלם", "tkt_escalated", "בוליאני"),
        ],
        [
            "קריאה בעדיפות גבוהה (3) שלא טופלה תוך 4 שעות מוסלמת אוטומטית (tkt_escalated = true).",
            "קריאה שכבר הוסלמה לא ניתנת להסלמה חוזרת.",
        ],
    ),
    (
        "50010", "אישור תשלום לספק", "תשלום ספק", "pay_vendor",
        [
            ("סטטוס תשלום", "pay_status", "קוד: 1=ממתין, 2=אושר, 3=נדחה"),
            ("סכום", "pay_amount", "מספרי"),
        ],
        [
            "תשלום מעל 20000 מחייב אישור כפול (שני מאשרים שונים) לפני מעבר לסטטוס אושר.",
            "תשלום נדחה (3) לא ניתן להעברה חוזרת לממתין.",
        ],
    ),
    (
        "50011", "בקשת חופשה לעובד", "בקשת חופשה", "lve_request",
        [
            ("סטטוס בקשה", "lve_status", "קוד: 1=ממתין, 2=אושר, 3=נדחה"),
            ("מספר ימים", "lve_days", "מספרי, חייב להיות גדול מ-0"),
        ],
        [
            "בקשה לכל התלוי ביתרת ימי החופשה של העובד — לא ניתן לאשר בקשה שחורגת מהיתרה.",
            "בקשה בת יום אחד או פחות מאושרת אוטומטית ללא צורך במנהל.",
        ],
    ),
    (
        "50012", "התראת חידוש מלאי", "פריט מלאי", "inv_item",
        [
            ("כמות במלאי", "inv_quantity", "מספרי"),
            ("סף חידוש", "inv_reorderthreshold", "מספרי"),
        ],
        [
            "כאשר inv_quantity יורד מתחת ל-inv_reorderthreshold, נוצרת התראת חידוש מלאי.",
            "פריט עם כמות 0 מסומן כ'אזל מהמלאי' בנוסף להתראה.",
        ],
    ),
    (
        "50013", "טיפול בתלונת לקוח", "תלונה", "cmp_complaint",
        [
            ("סטטוס תלונה", "cmp_status", "קוד: 1=פתוחה, 2=בטיפול, 3=נסגרה"),
            ("פתרון", "cmp_resolution", "טקסט, מתמלא בסגירה"),
        ],
        [
            "תלונה לא ניתנת לסגירה (3) ללא פתרון מתועד (cmp_resolution לא ריק).",
            "תלונה פתוחה מעל 14 יום מסומנת לבדיקת מנהל.",
        ],
    ),
    (
        "50014", "הנפקת שובר מתנה", "שובר מתנה", "gft_giftcard",
        [
            ("סטטוס שובר", "gft_status", "קוד: 1=פעיל, 2=מומש, 3=פג תוקף"),
            ("יתרה", "gft_balance", "מספרי"),
        ],
        [
            "שובר עם יתרה 0 עובר אוטומטית לסטטוס מומש (2).",
            "לא ניתן להשתמש בשובר שפג תוקפו (3), גם אם יש בו יתרה.",
        ],
    ),
    (
        "50015", "בקשת השבתת חשבון", "בקשת השבתה", "dea_deactivation",
        [
            ("סטטוס בקשה", "dea_status", "קוד: 1=ממתין, 2=אושר, 3=בוטל ע\"י המשתמש"),
            ("סיבה", "dea_reason", "טקסט"),
        ],
        [
            "השבתת חשבון עם מנוי פעיל דורשת קודם ביטול המנוי (ראה תיוג 50004).",
            "בקשה שבוטלה ע\"י המשתמש (3) לא מבצעת שום שינוי בחשבון.",
        ],
    ),
]


def build() -> Path:
    d = docx.Document()
    d.add_heading("אפיון מרוכז — 15 תהליכים עסקיים נפרדים", level=1)
    d.add_paragraph(
        "מסמך זה מרכז 15 תהליכים עסקיים בלתי-תלויים, כל אחד עם תיוג משימה משלו. "
        "מטרת המסמך: לבדוק שהסוכן מפיק תסריטים אך ורק עבור התיוג המבוקש, "
        "ולא מערבב תוכן מתהליכים אחרים המופיעים במסמך."
    )

    for tag, title, entity_he, entity_tech, fields, rules in SECTIONS:
        d.add_heading(f"תיוג משימה {tag}: {title}", level=2)
        d.add_paragraph(f'ישות "{entity_he}" ({entity_tech}):')

        table = d.add_table(rows=1, cols=3)
        table.rows[0].cells[0].text = "שם עברי"
        table.rows[0].cells[1].text = "שם טכני"
        table.rows[0].cells[2].text = "הערות"
        for he, tech, note in fields:
            cells = table.add_row().cells
            cells[0].text, cells[1].text, cells[2].text = he, tech, note

        d.add_paragraph("חוקים עסקיים:")
        for rule in rules:
            d.add_paragraph(rule, style="List Bullet")

    out = Path(__file__).with_name("multi_tag_sample_spec.docx")
    d.save(out)
    return out


if __name__ == "__main__":
    build()
    print("Wrote multi_tag_sample_spec.docx")
