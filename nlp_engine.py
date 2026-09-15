"""
Core matching engine.

Skill extraction primarily uses spaCy's PhraseMatcher against a curated
skills dictionary (spacy.blank("en") -- this only needs the spaCy
*library*, not a downloaded language model, so `pip install spacy` is
enough; no `python -m spacy download ...` step required).

If spaCy is not installed for any reason, we fall back to a pure
regex-based matcher so the app still works end-to-end.

Overall match score = weighted blend of:
  - skill coverage  (how many of the JD's required skills appear in the resume)
  - TF-IDF cosine similarity of the full resume text vs. the full JD text
"""

import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from skills_data import SKILLS

_CANONICAL = {s.lower(): s for s in SKILLS}

try:
    import spacy
    from spacy.matcher import PhraseMatcher

    _nlp = spacy.blank("en")
    _matcher = PhraseMatcher(_nlp.vocab, attr="LOWER")
    _patterns = [_nlp.make_doc(skill) for skill in SKILLS]
    _matcher.add("SKILLS", _patterns)
    _USE_SPACY = True
except ImportError:
    _USE_SPACY = False


def _extract_skills_spacy(text: str) -> set:
    doc = _nlp.make_doc(text)
    matches = _matcher(doc)
    found = set()
    for _, start, end in matches:
        span_text = doc[start:end].text.strip().lower()
        if span_text in _CANONICAL:
            found.add(_CANONICAL[span_text])
    return found


def _extract_skills_regex(text: str) -> set:
    found = set()
    lowered = text.lower()
    for skill in SKILLS:
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(skill.lower()) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, lowered):
            found.add(skill)
    return found


def extract_skills(text: str) -> set:
    if not text or not text.strip():
        return set()
    if _USE_SPACY:
        return _extract_skills_spacy(text)
    return _extract_skills_regex(text)


def tfidf_similarity(text_a: str, text_b: str) -> float:
    if not text_a.strip() or not text_b.strip():
        return 0.0
    vectorizer = TfidfVectorizer(stop_words="english")
    try:
        tfidf = vectorizer.fit_transform([text_a, text_b])
    except ValueError:
        # Happens if both texts are entirely stop-words / empty after cleaning
        return 0.0
    sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
    return float(sim)


def analyze_match(resume_text: str, jd_text: str) -> dict:
    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(jd_text)

    matched = sorted(resume_skills & jd_skills)
    missing = sorted(jd_skills - resume_skills)

    skill_coverage = (len(matched) / len(jd_skills)) if jd_skills else 0.0
    text_similarity = tfidf_similarity(resume_text, jd_text)

    if jd_skills:
        final_score = 0.65 * skill_coverage + 0.35 * text_similarity
    else:
        # No recognizable skills in the JD -- fall back to plain text similarity
        final_score = text_similarity

    return {
        "match_score": round(final_score * 100, 1),
        "matched_skills": matched,
        "missing_skills": missing,
        "skill_coverage": round(skill_coverage * 100, 1),
        "text_similarity": round(text_similarity * 100, 1),
    }
