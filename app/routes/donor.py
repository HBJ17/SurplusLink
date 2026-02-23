"""Donor routes."""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app import db
from app.models import FoodPost, User, Rating
from app.services.notification_service import notify_food_request_accepted, notify_delivery_completed
from app.services.rating_service import create_rating

donor_bp = Blueprint('donor', __name__)


def donor_required(f):
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_donor:
            flash('Donor access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapped


@donor_bp.route('/dashboard')
@login_required
@donor_required
def dashboard():
    from app.services.location_service import mark_expired_posts
    mark_expired_posts()
    posts = FoodPost.query.filter_by(donor_id=current_user.id).order_by(FoodPost.created_at.desc()).all()
    return render_template('donor/dashboard.html', posts=posts)


@donor_bp.route('/post/create', methods=['GET', 'POST'])
@login_required
@donor_required
def create_post():
    if request.method == 'POST':
        food_type = request.form.get('food_type', '').strip()
        quantity = request.form.get('quantity', type=int) or 0
        expiry_hours = request.form.get('expiry_hours', type=int) or 4
        delivery_type = request.form.get('delivery_type', 'pickup')
        lat = request.form.get('latitude', type=float)
        lon = request.form.get('longitude', type=float)
        address = request.form.get('address', '').strip()

        if not food_type or quantity <= 0:
            flash('Food type and quantity are required.', 'error')
            return render_template('donor/create_post.html')

        if lat is None or lon is None:
            lat = current_user.latitude
            lon = current_user.longitude
        if lat is None or lon is None:
            flash('Please set the pickup/delivery point: use "Auto-detect my location" or click on the map.', 'error')
            return render_template('donor/create_post.html')

        expiry_time = datetime.utcnow() + timedelta(hours=expiry_hours)
        post = FoodPost(
            donor_id=current_user.id,
            food_type=food_type,
            quantity=quantity,
            expiry_time=expiry_time,
            delivery_type=delivery_type,
            latitude=lat,
            longitude=lon,
            address=address or None
        )
        db.session.add(post)
        db.session.commit()
        flash('Food post created successfully.', 'success')
        return redirect(url_for('donor.dashboard'))
    return render_template('donor/create_post.html')


@donor_bp.route('/post/<int:post_id>')
@login_required
@donor_required
def post_detail(post_id):
    post = FoodPost.query.get_or_404(post_id)
    if post.donor_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('donor.dashboard'))
    ngo = User.query.get(post.ngo_id) if post.ngo_id else None
    return render_template('donor/post_detail.html', post=post, ngo=ngo)


@donor_bp.route('/api/post/<int:post_id>/location')
@login_required
@donor_required
def post_location(post_id):
    post = FoodPost.query.get_or_404(post_id)
    if post.donor_id != current_user.id:
        return jsonify({'error': 'Forbidden'}), 403
    ngo = post.ngo
    return jsonify({
        'donor_lat': post.latitude,
        'donor_lon': post.longitude,
        'ngo_lat': ngo.latitude if ngo else None,
        'ngo_lon': ngo.longitude if ngo else None,
    })


@donor_bp.route('/api/post/<int:post_id>/status')
@login_required
@donor_required
def post_status(post_id):
    post = FoodPost.query.get_or_404(post_id)
    if post.donor_id != current_user.id:
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify({
        'status': post.status,
        'delivered_at': post.delivered_at.isoformat() if post.delivered_at else None,
    })


@donor_bp.route('/post/<int:post_id>/rate-ngo', methods=['GET', 'POST'])
@login_required
@donor_required
def rate_ngo(post_id):
    post = FoodPost.query.get_or_404(post_id)
    if post.donor_id != current_user.id or post.status != 'delivered':
        flash('You can only rate completed deliveries.', 'error')
        return redirect(url_for('donor.dashboard'))
    ngo = post.ngo
    if not ngo:
        flash('No NGO to rate.', 'error')
        return redirect(url_for('donor.dashboard'))

    existing = Rating.query.filter_by(
        food_id=post_id, rater_id=current_user.id, rated_id=ngo.id
    ).first()
    if existing:
        flash('You have already rated this NGO.', 'info')
        return redirect(url_for('donor.dashboard'))

    if request.method == 'POST':
        rating_value = request.form.get('rating', type=int) or 5
        feedback = request.form.get('feedback', '').strip()
        create_rating(
            donor_id=post.donor_id, ngo_id=ngo.id, food_id=post.id,
            rater_id=current_user.id, rated_id=ngo.id,
            rating_value=rating_value, feedback=feedback
        )
        flash('Thank you for your rating!', 'success')
        return redirect(url_for('donor.dashboard'))

    return render_template('donor/rate_ngo.html', post=post, ngo=ngo)


@donor_bp.route('/api/update-location', methods=['POST'])
@login_required
@donor_required
def update_location():
    lat = request.json.get('latitude', type=float)
    lon = request.json.get('longitude', type=float)
    if lat is not None and lon is not None:
        current_user.latitude = lat
        current_user.longitude = lon
        db.session.commit()
        return jsonify({'ok': True})
    return jsonify({'error': 'Invalid coordinates'}), 400


