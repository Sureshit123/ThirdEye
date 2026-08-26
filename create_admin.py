from app import app
from models import db, User

def add_admin_user():
    """Creates the admin user if it doesn't exist."""
    with app.app_context():
        # Check if the admin user already exists
        if User.query.filter_by(username='admin').first():
            print("Admin user already exists.")
            return

        # Create the admin user with the password 'password123'
        # The User model's __init__ method handles the hashing
        admin_user = User(username='admin', password='password123', role='admin')

        db.session.add(admin_user)
        db.session.commit()
        print("Admin user (admin/password123) created successfully!")

if __name__ == '__main__':
    add_admin_user()