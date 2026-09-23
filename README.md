# Forensic Face Sketch Construction and Recognition

A Flask web application that allows users to construct a face sketch from a photo, compare a sketch against a known person database, and perform face matching using facial encoding and similarity detection.

## Project Overview

This project is designed for forensic-style face sketch matching and recognition. It includes:

- User registration and login
- Admin dashboard for managing person records
- Uploading face images for storage and encoding
- Converting a photo into a pencil-sketch style image
- Matching a submitted sketch against known persons
- Facial recognition using `face_recognition` and OpenCV

## Tech Stack

- Python
- Flask
- Flask-SQLAlchemy
- Flask-Bcrypt
- OpenCV
- NumPy
- face_recognition
- SQLite (default database)

## Project Structure

```text
Forensic Face Sketch Construction and Recognition/
├── app.py                  # Flask application and routes
├── models.py               # Database models
├── utils.py                # Image processing and recognition logic
├── requirements.txt        # Python dependencies
├── create_admin.py         # Helper to create admin accounts
├── create_user.py          # Helper to create user accounts
├── instance/               # Local instance data
├── model/                  # Project-related model files/data
├── static/                 # CSS, JS, uploads, images, and other frontend assets
├── templates/              # HTML templates
└── .gitignore
```

## Features

### Admin Features
- Manage person records
- Add a person with name, details, and image
- Delete a stored person record
- View all persons in the admin dashboard

### User Features
- Register a new account
- Log in to the app
- Construct a sketch from a photo
- Upload a sketch for recognition
- View top matching candidates from the database

## Installation

1. Clone or open the project folder.
2. Create and activate a virtual environment:

```bash
python -m venv venv
```

On Windows:

```bash
venv\Scripts\activate
```

On macOS/Linux:

```bash
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

> Note: Some packages such as `dlib` and `face_recognition` may require additional system-level dependencies depending on your OS. On Windows, ensure Python and compatible build tools are installed.

## Database Initialization

Run the Flask database setup command:

```bash
flask --app app init-db
```

This creates the SQLite database and adds a default admin user:

- Username: `admin`
- Password: `password123`

## Run the Application

Start the Flask app:

```bash
python app.py
```

Then open the app in your browser:

```text
http://127.0.0.1:5000/
```

## Default Routes

- `/` - Home page
- `/login` - User login
- `/register` - New user registration
- `/sketch` - Sketch creation interface
- `/recognition` - Sketch recognition flow
- `/photo-to-sketch` - Convert photo to sketch
- `/admin/dashboard` - Admin control panel

## Notes

- The app stores images in `static/person_db` and sketch uploads in `static/uploads`.
- The default database is SQLite and is configured in `app.py`.
- For production usage, you should change the `SECRET_KEY` and secure the admin password.
- The system uses face encodings stored as text in the database for similarity comparison.

## Security Reminder

Before deploying or using the app in a production environment:

- Replace the hardcoded `SECRET_KEY`
- Set stronger admin credentials
- Consider moving from SQLite to a production database
- Validate uploaded files more strictly

## License

This project is for educational and academic use unless otherwise specified by the repository owner.
