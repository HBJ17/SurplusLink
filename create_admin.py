"""Create an admin user (run once for setup)."""
#imports
import sys
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    email = sys.argv[1] if len(sys.argv) > 1 else 'admin@surpluslink.local'
    name = sys.argv[2] if len(sys.argv) > 2 else 'Admin'
    password = sys.argv[3] if len(sys.argv) > 3 else 'admin123'
    if User.query.filter_by(email=email).first():
        print(f'User {email} already exists.')
    else:
        u = User(name=name, email=email, role='admin')
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        print(f'Admin created: {email} / {password}')
