# create_user.py
from app import app
from models import db, User

def add_user(username, password, role='user'):
    """
    Creates a new user with a securely hashed password.
    """
    # The app_context is necessary to connect to the database
    with app.app_context():
        # Check if the user already exists to avoid errors
        if User.query.filter_by(username=username).first():
            print(f"User '{username}' already exists.")
            return

        # Create a new User object. 
        # The __init__ method in the User model automatically handles password hashing.
        new_user = User(username=username, password=password, role=role)
        
        # Add the new user to the database session
        db.session.add(new_user)
        
        # Commit the changes to save the user to the database
        db.session.commit()
        
        print(f"User '{username}' with role '{role}' created successfully!")
        print("You can now log in with this account.")

if __name__ == '__main__':
    # --- Define the new user's credentials here ---
    new_username = 'artist'
    new_password = 'userpass'
    
    # Call the function to add the user
    add_user(new_username, new_password)