"""
Content-based recommendation service.

Uses user preferences (genres, pacing, tone, themes, moods) to find matching books.
"""

from sqlalchemy import select, or_, and_, func, text, case, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from typing import Optional

from app.models import Book, UserPreference


def get_personalized_recommendations(
    session: Session,
    user_id: int,
    limit: int = 20
) -> list[Book]:
    """
    Get personalized book recommendations based on user preferences.
    
    Matching strategy:
    1. Filter by favorite genres (OR match)
    2. Match pacing preference
    3. Match tone preference  
    4. Match preferred themes (overlap)
    5. Match preferred moods (overlap)
    6. Exclude disliked genres
    7. Exclude books with content warnings matching triggers
    """
    
    # Fetch user preferences
    prefs = session.query(UserPreference).filter(
        UserPreference.user_id == user_id
    ).first()
    
    if not prefs:
        # No preferences set, return popular/random books
        return session.query(Book).order_by(func.random()).limit(limit).all()
    
    # Start building the query
    query = session.query(Book)
    
    # --- Filtering ---
    
    # Exclude disliked genres (genres field is comma-separated string)
    if prefs.disliked_genres:
        for genre in prefs.disliked_genres:
            query = query.filter(~Book.genres.ilike(f"%{genre}%"))
    
    # Exclude books with content warnings matching triggers
    if prefs.triggers_to_avoid:
        for trigger in prefs.triggers_to_avoid:
            # content_warnings is a JSON array, check if trigger is in it
            query = query.filter(
                or_(
                    Book.content_warnings == None,
                    ~Book.content_warnings.cast(str).ilike(f"%{trigger}%")
                )
            )
    
    # --- Scoring (using CASE expressions for ranking) ---
    # We'll use a scoring approach: books that match more criteria rank higher
    
    score_cases = []
    
    # Genre matching (+3 points per matching genre)
    if prefs.favorite_genres:
        for genre in prefs.favorite_genres:
            score_cases.append(
                case((Book.genres.ilike(f"%{genre}%"), 3), else_=0)
            )
    
    # Pacing match (+2 points)
    if prefs.pacing_preference:
        score_cases.append(
            case((Book.pacing == prefs.pacing_preference, 2), else_=0)
        )
    
    # Tone match (+2 points)
    if prefs.tone_preference:
        score_cases.append(
            case((Book.tone.ilike(f"%{prefs.tone_preference}%"), 2), else_=0)
        )
    
    # Theme matching (+1 point per matching theme)
    if prefs.preferred_themes:
        for theme in prefs.preferred_themes:
            score_cases.append(
                case((Book.themes.cast(String).ilike(f"%{theme}%"), 1), else_=0)
            )
    
    # Mood matching (+1 point per matching mood)
    if prefs.preferred_moods:
        for mood in prefs.preferred_moods:
            score_cases.append(
                case((Book.mood_tags.cast(String).ilike(f"%{mood}%"), 1), else_=0)
            )
    
    # Calculate total score
    if score_cases:
        total_score = sum(score_cases)
        query = query.add_columns(total_score.label("match_score"))
        query = query.order_by(total_score.desc(), func.random())
    else:
        query = query.order_by(func.random())
    
    # Limit results
    results = query.limit(limit).all()
    
    # Extract just the Book objects (score is in index 1 if present)
    if score_cases:
        return [row[0] for row in results]
    return results


def get_available_themes(session: Session, limit: int = 30) -> list[str]:
    """Get unique themes from enriched books for the onboarding UI, sorted by popularity."""
    from collections import Counter
    
    # Query themes from all books
    books_with_themes = session.query(Book.themes).filter(
        Book.themes.isnot(None),
        func.jsonb_array_length(Book.themes.cast(JSONB)) > 0
    ).all()
    
    # Count frequency of each theme
    theme_counter = Counter()
    for (themes,) in books_with_themes:
        if themes:
            for theme in themes:
                # Normalize: title case for display
                theme_counter[theme.strip().title()] += 1
    
    # Return top themes sorted by frequency (most popular first)
    return [theme for theme, count in theme_counter.most_common(limit)]


def get_available_moods(session: Session, limit: int = 30) -> list[str]:
    """Get unique moods from enriched books for the onboarding UI, sorted by popularity."""
    from collections import Counter
    
    # Query moods from all books
    books_with_moods = session.query(Book.mood_tags).filter(
        Book.mood_tags.isnot(None),
        func.jsonb_array_length(Book.mood_tags.cast(JSONB)) > 0
    ).all()
    
    # Count frequency of each mood
    mood_counter = Counter()
    for (moods,) in books_with_moods:
        if moods:
            for mood in moods:
                # Normalize: title case for display
                mood_counter[mood.strip().title()] += 1
    
    # Return top moods sorted by frequency (most popular first)
    return [mood for mood, count in mood_counter.most_common(limit)]
