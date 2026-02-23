"""Database models."""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(256), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(32), nullable=False)  # donor, ngo, admin
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    average_rating = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    food_posts = db.relationship('FoodPost', backref='donor', lazy='dynamic', foreign_keys='FoodPost.donor_id')
    ratings_received = db.relationship('Rating', backref='rated_user', lazy='dynamic', foreign_keys='Rating.rated_id')
    ratings_given = db.relationship('Rating', backref='rater', lazy='dynamic', foreign_keys='Rating.rater_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_donor(self):
        return self.role == 'donor'

    @property
    def is_ngo(self):
        return self.role == 'ngo'

    @property
    def is_admin(self):
        return self.role == 'admin'

    def __repr__(self):
        return f'<User {self.email}>'


class FoodPost(db.Model):
    __tablename__ = 'food_post'

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    food_type = db.Column(db.String(256), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)  # number of portions
    expiry_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(32), default='available')  # available, accepted, delivered, expired
    delivery_type = db.Column(db.String(32), default='pickup')  # pickup, delivery
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(512))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # When NGO accepts - auto-assign
    ngo_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ngo = db.relationship('User', foreign_keys=[ngo_id])
    accepted_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)

    ratings = db.relationship('Rating', backref='food_post', lazy='dynamic', foreign_keys='Rating.food_id')

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expiry_time

    @property
    def expires_soon(self):
        from datetime import timedelta
        return self.expiry_time - datetime.utcnow() <= timedelta(hours=2)

    def __repr__(self):
        return f'<FoodPost {self.id} {self.food_type}>'


class Rating(db.Model):
    __tablename__ = 'rating'

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ngo_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    food_id = db.Column(db.Integer, db.ForeignKey('food_post.id'), nullable=False)
    rater_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # who gave the rating
    rated_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # who received the rating
    rating_value = db.Column(db.Integer, nullable=False)  # 1-5
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
