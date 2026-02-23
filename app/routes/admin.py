"""Admin routes."""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, send_file, flash, redirect
from flask_login import login_required, current_user
import io
import csv

from app import db
from app.models import FoodPost, User, Rating

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapped


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    posts = FoodPost.query.order_by(FoodPost.created_at.desc()).all()

    # Metrics
    total_quantity = sum(p.quantity for p in posts if p.status == 'delivered')
    delivered = FoodPost.query.filter_by(status='delivered').count()
    total_posts = FoodPost.query.count()
    donors = User.query.filter_by(role='donor').count()
    ngos = User.query.filter_by(role='ngo').count()

    # Average trust (average of all users with ratings)
    rated_users = User.query.filter(User.average_rating > 0).all()
    avg_trust = sum(u.average_rating for u in rated_users) / len(rated_users) if rated_users else 0

    # Top donors by delivered posts
    donor_counts = {}
    for p in FoodPost.query.filter_by(status='delivered').all():
        donor_counts[p.donor_id] = donor_counts.get(p.donor_id, 0) + 1
    top_donor_ids = sorted(donor_counts, key=donor_counts.get, reverse=True)[:5]
    top_donors = [User.query.get(i) for i in top_donor_ids if User.query.get(i)]

    return render_template('admin/dashboard.html',
                          posts=posts,
                          total_quantity=total_quantity,
                          delivered_count=delivered,
                          total_posts=total_posts,
                          donors_count=donors,
                          ngos_count=ngos,
                          avg_trust=round(avg_trust, 2),
                          top_donors=top_donors)


@admin_bp.route('/posts')
@login_required
@admin_required
def posts():
    posts = FoodPost.query.order_by(FoodPost.created_at.desc()).all()
    return render_template('admin/posts.html', posts=posts)


@admin_bp.route('/export/csv')
@login_required
@admin_required
def export_csv():
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    if not year:
        year = datetime.utcnow().year
    if not month:
        month = datetime.utcnow().month

    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        end = datetime(year, month + 1, 1) - timedelta(seconds=1)

    posts = FoodPost.query.filter(
        FoodPost.created_at >= start,
        FoodPost.created_at <= end
    ).order_by(FoodPost.created_at).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Donor Name', 'Donor Email', 'Food Type', 'Quantity', 'Status',
                     'NGO Name', 'NGO Email', 'Accepted At', 'Delivered At', 'Created At'])
    for p in posts:
        donor = p.donor
        ngo = p.ngo
        writer.writerow([
            p.id, donor.name, donor.email, p.food_type, p.quantity, p.status,
            ngo.name if ngo else '', ngo.email if ngo else '',
            p.accepted_at.isoformat() if p.accepted_at else '',
            p.delivered_at.isoformat() if p.delivered_at else '',
            p.created_at.isoformat()
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'surplus_link_report_{year}_{month:02d}.csv'
    )


