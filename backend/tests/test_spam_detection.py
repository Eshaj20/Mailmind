from app.services.spam_detection import detect_spam_fields
from scripts.evaluate_spam_detector import evaluate_rows


def test_spam_detector_flags_obvious_prize_spam():
    result = detect_spam_fields(
        subject="You have won a cash reward",
        sender="winner@unknown.example",
        snippet="Claim your prize now. Verify your account immediately.",
        body_preview="Click here to claim your urgent reward.",
    )

    assert result.label == "spam"
    assert result.score >= 0.7
    assert result.model_version.endswith("v1")


def test_spam_detector_keeps_normal_interview_email_ham():
    result = detect_spam_fields(
        subject="Backend interview schedule",
        sender="recruiter@example.com",
        snippet="Can we schedule your interview this week?",
        body_preview="Please share your availability.",
    )

    assert result.label == "ham"
    assert result.score < 0.7


def test_spam_evaluation_scores_public_dataset_rows():
    rows = [
        {"text": "You have won a lottery prize. Claim your reward now.", "label": "spam"},
        {"text": "Can we schedule your backend interview this week?", "label": "ham"},
    ]

    metrics = evaluate_rows(rows)

    assert metrics["sample_count"] == 2
    assert metrics["true_positive"] == 1
    assert metrics["true_negative"] == 1
    assert metrics["f1"] == 1.0