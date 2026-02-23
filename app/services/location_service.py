"""Location-based services using Haversine formula."""
import math
from datetime import datetime

from flask import current_app




def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in km using Haversine formula."""
    R = 6371  # Earth's radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def mark_expired_posts():
    """Mark posts past expiry_time as expired."""
    from app.models import FoodPost
    from app import db
    FoodPost.query.filter(
        FoodPost.status == 'available',
        FoodPost.expiry_time <= datetime.utcnow()
    ).update({FoodPost.status: 'expired'}, synchronize_session=False)
    db.session.commit()


def get_nearby_food_posts(ngo_lat: float, ngo_lon: float, radius_km: float = None):
    """
    Fetch nearby available food posts within radius, sorted by distance.
    Excludes expired posts.
    """
    from app.models import FoodPost

    if radius_km is None:
        radius_km = current_app.config.get('MATCH_RADIUS_KM', 25)

    mark_expired_posts()
    posts = FoodPost.query.filter(
        FoodPost.status == 'available',
        FoodPost.expiry_time > datetime.utcnow()
    ).all()

    results = []
    for post in posts:
        dist = haversine_km(ngo_lat, ngo_lon, post.latitude, post.longitude)
        if dist <= radius_km:
            results.append({
                'post': post,
                'distance_km': round(dist, 2)
            })

    results.sort(key=lambda x: x['distance_km'])
    return results


def estimate_travel_time_seconds(distance_km: float, avg_speed_kmh: float = 25) -> float:
    """Estimate travel time in seconds. Default 25 km/h average city speed."""
    hours = distance_km / avg_speed_kmh
    return hours * 3600
