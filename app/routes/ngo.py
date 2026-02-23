"""NGO routes."""
import threading
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app import db
from app.models import FoodPost, User, Rating
from app.services.location_service import get_nearby_food_posts, haversine_km, estimate_travel_time_seconds
from app.services.notification_service import notify_food_request_accepted, notify_delivery_started, notify_delivery_completed
from app.services.rating_service import create_rating

ngo_bp = Blueprint('ngo', __name__)



def ngo_required(f):
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_ngo:
            flash('NGO access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapped


@ngo_bp.route('/dashboard')
@login_required
@ngo_required
def dashboard():
    lat = current_user.latitude
    lon = current_user.longitude
    nearby = []
    if lat is not None and lon is not None:
        radius = request.args.get('radius', type=float) or 25
        nearby = get_nearby_food_posts(lat, lon, radius_km=radius)

    # Accepted/delivered posts for this NGO
    my_posts = FoodPost.query.filter(
        FoodPost.ngo_id == current_user.id,
        FoodPost.status.in_(['accepted', 'delivered'])
    ).order_by(FoodPost.accepted_at.desc()).all()

    return render_template('ngo/dashboard.html', nearby=nearby, my_posts=my_posts)


@ngo_bp.route('/post/<int:post_id>/accept', methods=['POST'])
@login_required
@ngo_required
def accept_post(post_id):
    post = FoodPost.query.get_or_404(post_id)
    if post.status != 'available':
        flash('This post is no longer available.', 'error')
        return redirect(url_for('ngo.dashboard'))

    if post.expiry_time < datetime.utcnow():
        post.status = 'expired'
        db.session.commit()
        flash('This post has expired.', 'error')
        return redirect(url_for('ngo.dashboard'))

    # Auto-assign this NGO
    post.ngo_id = current_user.id
    post.status = 'accepted'
    post.accepted_at = datetime.utcnow()
    db.session.commit()

    notify_food_request_accepted(post.donor.email, current_user.name, post.food_type)
    flash('You have accepted the food.', 'success')
    if post.delivery_type == 'delivery':
        return redirect(url_for('ngo.track_delivery', post_id=post_id))
    return redirect(url_for('ngo.dashboard'))


@ngo_bp.route('/track/<int:post_id>')
@login_required
@ngo_required
def track_delivery(post_id):
    post = FoodPost.query.get_or_404(post_id)
    if post.ngo_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('ngo.dashboard'))
    donor = post.donor
    # Use post lat/lon for pickup point (where food is), NGO lat/lon for destination
    donor_lat = post.latitude
    donor_lon = post.longitude
    ngo_lat = current_user.latitude
    ngo_lon = current_user.longitude
    if ngo_lat is None or ngo_lon is None:
        ngo_lat, ngo_lon = donor_lat, donor_lon  # fallback
    distance_km = haversine_km(donor_lat, donor_lon, ngo_lat, ngo_lon)
    est_seconds = estimate_travel_time_seconds(distance_km)
    return render_template('ngo/track_delivery.html', post=post, donor=donor,
                          donor_lat=donor_lat, donor_lon=donor_lon, ngo_lat=ngo_lat, ngo_lon=ngo_lon,
                          distance_km=round(distance_km, 2), est_minutes=int(est_seconds / 60))


@ngo_bp.route('/api/post/<int:post_id>/start-delivery', methods=['POST'])
@login_required
@ngo_required
def start_delivery(post_id):
    post = FoodPost.query.get_or_404(post_id)
    if post.ngo_id != current_user.id:
        return jsonify({'error': 'Forbidden'}), 403
    if post.status != 'accepted':
        return jsonify({'error': 'Invalid state'}), 400
    # Send email in background (SMTP may block)
    donor_email = post.donor.email
    ngo_email = current_user.email
    food_type = post.food_type
    def _send():
        try:
            notify_delivery_started(donor_email, ngo_email, food_type)
        except Exception:
            pass
    threading.Thread(target=_send).start()
    return jsonify({'ok': True, 'status': 'in_progress'})


@ngo_bp.route('/api/post/<int:post_id>/complete-pickup', methods=['POST'])
@login_required
@ngo_required
def complete_pickup(post_id):
    """Mark pickup order as complete (simplified flow for pickup mode)."""
    post = FoodPost.query.get_or_404(post_id)
    if post.ngo_id != current_user.id:
        return jsonify({'error': 'Forbidden'}), 403
    if post.delivery_type != 'pickup':
        return jsonify({'error': 'Not a pickup order'}), 400
    if post.status != 'accepted':
        return jsonify({'error': 'Invalid state'}), 400

    post.status = 'delivered'
    post.delivered_at = datetime.utcnow()
    db.session.commit()

    donor_email = post.donor.email
    ngo_email = current_user.email
    food_type = post.food_type
    def _send():
        try:
            notify_delivery_completed(donor_email, ngo_email, food_type)
        except Exception:
            pass
    threading.Thread(target=_send).start()

    return jsonify({'ok': True, 'status': 'delivered'})


@ngo_bp.route('/api/post/<int:post_id>/confirm-delivery', methods=['POST'])
@login_required
@ngo_required
def confirm_delivery(post_id):
    post = FoodPost.query.get_or_404(post_id)
    if post.ngo_id != current_user.id:
        return jsonify({'error': 'Forbidden'}), 403
    if post.status not in ('accepted', 'available'):
        return jsonify({'error': 'Invalid state'}), 400

    post.status = 'delivered'
    post.delivered_at = datetime.utcnow()
    db.session.commit()

    # Send email in background so response returns immediately (SMTP may block/hang)
    donor_email = post.donor.email
    ngo_email = current_user.email
    food_type = post.food_type
    def _send():
        try:
            notify_delivery_completed(donor_email, ngo_email, food_type)
        except Exception:
            pass
    threading.Thread(target=_send).start()

    return jsonify({'ok': True, 'status': 'delivered'})


@ngo_bp.route('/post/<int:post_id>/rate', methods=['GET', 'POST'])
@login_required
@ngo_required
def rate_donor(post_id):
    post = FoodPost.query.get_or_404(post_id)
    if post.ngo_id != current_user.id or post.status != 'delivered':
        flash('You can only rate completed deliveries.', 'error')
        return redirect(url_for('ngo.dashboard'))

    existing = Rating.query.filter_by(
        food_id=post_id, rater_id=current_user.id, rated_id=post.donor_id
    ).first()
    if existing:
        flash('You have already rated this donor.', 'info')
        return redirect(url_for('ngo.dashboard'))

    if request.method == 'POST':
        rating_value = request.form.get('rating', type=int) or 5
        feedback = request.form.get('feedback', '').strip()
        create_rating(
            donor_id=post.donor_id, ngo_id=current_user.id, food_id=post.id,
            rater_id=current_user.id, rated_id=post.donor_id,
            rating_value=rating_value, feedback=feedback
        )
        flash('Thank you for your rating!', 'success')
        return redirect(url_for('ngo.dashboard'))

    return render_template('ngo/rate_donor.html', post=post)


@ngo_bp.route('/api/update-location', methods=['POST'])
@login_required
@ngo_required
def update_location():
    data = request.get_json(silent=True) or {}
    lat = data.get('latitude')
    lon = data.get('longitude')
    if lat is not None and lon is not None:
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid coordinates'}), 400
        current_user.latitude = lat
        current_user.longitude = lon
        db.session.commit()
        return jsonify({'ok': True})
    return jsonify({'error': 'Invalid coordinates'}), 400
