"""Answer Evaluation Engine — TF-IDF vectorization + Cosine Similarity."""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rapidfuzz import fuzz
import re
import logging

# Weights for final score calculation
WEIGHT_TFIDF = 0.4
WEIGHT_FUZZY = 0.6

def evaluate_answer(student_text, model_text):

    if not student_text or not model_text:
        return 0.0

    try:

        logging.debug("MODEL TEXT: %s", model_text[:200])
        logging.debug("STUDENT TEXT: %s", student_text[:200])

        # TF-IDF similarity
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([model_text, student_text])
        tfidf_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]

        # Fuzzy similarity (handles OCR spelling errors)
        fuzzy_score = fuzz.token_set_ratio(model_text, student_text) / 100

        logging.debug("TFIDF SCORE: %s", tfidf_score)
        logging.debug("FUZZY SCORE: %s", fuzzy_score)

        # Final similarity (weighted)
        final_score = (WEIGHT_TFIDF * tfidf_score) + (WEIGHT_FUZZY * fuzzy_score)

        logging.debug("FINAL SIMILARITY: %s", final_score)

        return max(0.0, min(1.0, final_score))

    except Exception as e:
        logging.error("Similarity error: %s", e)
        return 0.0


STOPWORDS = {
    "the","is","a","an","this","that","these","those","and","or",
    "in","on","at","for","of","to","with","as","by","from",
    "it","be","are","was","were","has","have","had","do","does"
}


def keyword_match_score(student_text, model_text):
    """
    OCR tolerant keyword matching using multiple fuzzy techniques.
    Optimized with early exit on exact match.
    """

    if not student_text or not model_text:
        return [], [], 0.0

    # extract words
    student_words = set(re.findall(r'\w+', student_text.lower()))
    model_words = set(re.findall(r'\w+', model_text.lower()))

    # remove stopwords
    model_keywords = [w for w in model_words if w not in STOPWORDS and len(w) > 3]

    matched = []
    missing = []

    for m_word in model_keywords:

        # Fast exact match check first (avoids expensive fuzzy ops)
        if m_word in student_words:
            matched.append(m_word)
            continue

        best_score = 0

        for s_word in student_words:

            # multiple fuzzy comparisons
            score1 = fuzz.ratio(m_word, s_word)
            score2 = fuzz.partial_ratio(m_word, s_word)
            score3 = fuzz.token_sort_ratio(m_word, s_word)

            similarity = max(score1, score2, score3)

            if similarity > best_score:
                best_score = similarity

            # Early exit if we found a strong enough match
            if best_score >= 85:
                break

        # OCR tolerant threshold
        if best_score >= 65:
            matched.append(m_word)
        else:
            missing.append(m_word)

    overlap = len(matched) / len(model_keywords) if model_keywords else 0.0

    return sorted(matched), sorted(missing), round(overlap, 4)