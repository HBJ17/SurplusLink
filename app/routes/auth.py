"""Authentication routes."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from app import db
from app.models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'donor')
        lat = request.form.get('latitude', type=float)
        lon = request.form.get('longitude', type=float)

        if not name or not email or not password:
            flash('Name, email and password are required.', 'error')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return render_template('auth/register.html')

        if role not in ('donor', 'ngo', 'admin'):
            role = 'donor'

        user = User(name=name, email=email, role=role)
        user.set_password(password)
        if lat is not None and lon is not None:
            user.latitude = lat
            user.longitude = lon
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return _redirect_by_role(user.role)
        flash('Invalid email or password.', 'error')
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


def _redirect_by_role(role: str):
    if role == 'donor':
        return redirect(url_for('donor.dashboard'))
    if role == 'ngo':
        return redirect(url_for('ngo.dashboard'))
    if role == 'admin':
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('auth.login'))


