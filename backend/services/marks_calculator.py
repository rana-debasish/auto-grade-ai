"""Marks Calculation Module — converts similarity scores into marks."""


def calculate_marks(similarity_score, total_marks, penalty=0.0):
    """
    Convert similarity score (0.0–1.0) into marks using piecewise grading.

    Thresholds tuned for hybrid similarity (keyword + TF-IDF + semantic):

        >= 0.75 → 90-100% marks (Excellent)
        >= 0.60 → 70-89% marks  (Good)
        >= 0.40 → 50-69% marks  (Average)
        >= 0.20 → 30-49% marks  (Below Average)
        <  0.20 → 0-29% marks   (Poor)
    """



    score = max(0.0, min(1.0, similarity_score))

    if score >= 0.70:
        # 88–100%
        percentage = 0.88 + (score - 0.70) * (0.12 / 0.30)

    elif score >= 0.55:
        # 68–87%
        percentage = 0.68 + (score - 0.55) * (0.20 / 0.15)

    elif score >= 0.35:
        # 48–67%
        percentage = 0.48 + (score - 0.35) * (0.20 / 0.20)

    elif score >= 0.18:
        # 28–47%
        percentage = 0.28 + (score - 0.18) * (0.20 / 0.17)

    else:
        # 0–27%
        percentage = score * (0.27 / 0.18)

    percentage = max(0.0, percentage - penalty)

    marks = round(percentage * total_marks)

    return min(marks, total_marks)

def get_grade(marks, total_marks):
    """Convert marks to a letter grade."""

    if total_marks <= 0:
        return 'N/A'

    pct = (marks / total_marks) * 100

    if pct >= 90:
        return 'O'
    elif pct >= 80:
        return 'A+'
    elif pct >= 70:
        return 'A'
    elif pct >= 60:
        return 'B+'
    elif pct >= 50:
        return 'B'
    elif pct >= 40:
        return 'C'
    else:
        return 'F'