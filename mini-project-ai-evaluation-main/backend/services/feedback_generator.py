"""Feedback Generation Module — auto-generates detailed evaluation feedback."""

from services.nlp_preprocessing import extract_keywords
from services.evaluation_engine import keyword_match_score
from services.marks_calculator import get_grade


def generate_feedback(student_answer, model_answer, similarity_score,
                      marks_obtained, total_marks):
    """
    Generate comprehensive feedback for a student submission.

    Returns a dict with:
    - grade: letter grade
    - similarity_percentage: human-readable similarity %
    - keyword_analysis: matched/missing keywords
    - strengths: what the student did well
    - weaknesses: areas for improvement
    - suggestions: actionable improvement tips
    """
    grade = get_grade(marks_obtained, total_marks)
    sim_pct = round(similarity_score * 100, 1)

    # Keyword analysis
    model_keywords = extract_keywords(model_answer)
    student_keywords = extract_keywords(student_answer)

    matched, missing, overlap = keyword_match_score(
        ' '.join(student_keywords),
        ' '.join(model_keywords)
    )

    # Build strengths
    strengths = []
    if sim_pct >= 70:
        strengths.append("Strong understanding of the topic demonstrated.")
    if sim_pct >= 50:
        strengths.append("Key concepts are present in the answer.")
    if len(matched) > len(model_keywords) * 0.5:
        strengths.append(f"Good keyword coverage — {len(matched)} out of {len(model_keywords)} key terms matched.")
    if len(student_answer.split()) > 50:
        strengths.append("Detailed answer with good elaboration.")

    if not strengths:
        strengths.append("Attempt made to answer the question.")

    # Build weaknesses
    weaknesses = []
    if sim_pct < 50:
        weaknesses.append("Answer has low relevance to the expected response.")
    if missing:
        top_missing = missing[:5]
        weaknesses.append(f"Missing key terms: {', '.join(top_missing)}")
    if len(student_answer.split()) < 20:
        weaknesses.append("Answer is too brief — more detail expected.")
    if sim_pct < 30:
        weaknesses.append("Significant gap between the submitted and expected answer.")

    # Build suggestions
    suggestions = []
    if missing:
        suggestions.append(f"Include these important concepts: {', '.join(missing[:5])}")
    if sim_pct < 60:
        suggestions.append("Review the topic thoroughly and provide more relevant content.")
    if len(student_answer.split()) < 30:
        suggestions.append("Elaborate your answer with examples and explanations.")
    if sim_pct >= 60 and sim_pct < 80:
        suggestions.append("Good effort! Add more specific details to improve your score.")
    if sim_pct >= 80:
        suggestions.append("Excellent work! Minor refinements could help achieve a perfect score.")

    return {
        'grade': grade,
        'similarity_percentage': sim_pct,
        'marks_obtained': marks_obtained,
        'total_marks': total_marks,
        'keyword_analysis': {
            'matched_keywords': matched,
            'missing_keywords': missing[:10],
            'keyword_overlap': round(overlap * 100, 1),
            'total_model_keywords': len(model_keywords),
        },
        'strengths': strengths,
        'weaknesses': weaknesses,
        'suggestions': suggestions,
    }
