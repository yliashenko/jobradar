"""Форматування Telegram-повідомлення: екранування, заголовок, посилання."""

from jobradar.core.notify import format_notification


def test_html_special_chars_escaped():
    job = {
        "title": "SDET & QA <Lead>",
        "company": "Ciklum",
        "salary": "$4500",
        "location": "віддалено",
        "source": "djinni",
        "url": "https://djinni.co/jobs/712345/",
    }
    row = {
        "score": 8.0,
        "band": "strong",
        "matched": ["TypeScript"],
        "gaps": ["pytest"],
        "verdict": "Сильний збіг.",
    }
    text = format_notification(job, row)
    assert "&lt;Lead&gt;" in text  # < > екрановані
    assert "8/10" in text  # скор у заголовку
    assert "https://djinni.co/jobs/712345/" in text


def test_no_score_no_slash_header():
    job = {
        "title": "QA",
        "company": "",
        "salary": "",
        "location": "",
        "source": "dou",
        "url": "u",
    }
    row = {"score": None, "band": "", "matched": [], "gaps": [], "verdict": ""}
    text = format_notification(job, row)
    assert "/10" not in text  # без оцінки — без дробу
