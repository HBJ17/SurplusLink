"""Rating and trust score services."""
from app import db
from app.models import User, Rating, FoodPost



def create_rating(donor_id: int, ngo_id: int, food_id: int, rater_id: int,
                  rated_id: int, rating_value: int, feedback: str = None) -> Rating:
    """Create a rating and update average for the rated user."""
    rating = Rating(
        donor_id=donor_id,
        ngo_id=ngo_id,
        food_id=food_id,
        rater_id=rater_id,
        rated_id=rated_id,
        rating_value=min(5, max(1, rating_value)),
        feedback=feedback
    )
    db.session.add(rating)
    db.session.commit()
    _update_average_rating(rated_id)
    return rating


def _update_average_rating(user_id: int):
    """Recalculate and update user's average rating."""
    ratings = Rating.query.filter(Rating.rated_id == user_id).all()
    if not ratings:
        return
    avg = sum(r.rating_value for r in ratings) / len(ratings)
    user = User.query.get(user_id)
    if user:
        user.average_rating = round(avg, 2)
        db.session.commit()
