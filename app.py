import os
import base64
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.utils import secure_filename
from models import db, User, Person, bcrypt
from utils import get_face_encoding, serialize_encoding, find_matches, convert_to_sketch_in_memory

# --- APP CONFIGURATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key' # Change this!
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:@localhost/thirdeye_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/person_db'
app.config['SKETCH_UPLOAD_FOLDER'] = 'static/uploads'

# --- INITIALIZE EXTENSIONS ---
db.init_app(app)
bcrypt.init_app(app)

# --- DECORATORS for access control ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# --- SETUP COMMAND ---
@app.cli.command("init-db")
def init_db_command():
    """Creates the database tables and a default admin."""
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password='password123', role='admin')
        db.session.add(admin_user)
        db.session.commit()
        print('Initialized the database and created admin user (admin/password123).')

# --- MAIN & AUTHENTICATION ROUTES ---
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash(f'Welcome, {user.username}!', 'success')
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('sketch_constructor'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('register'))
        new_user = User(username=username, password=password, role='user')
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

# --- ADMIN ROUTES ---
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    persons = Person.query.all()
    return render_template('admin_dashboard.html', persons=persons)

@app.route('/admin/add_person', methods=['POST'])
@admin_required
def add_person():
    name = request.form['name']
    details = request.form['person_details']
    if 'photo' not in request.files or request.files['photo'].filename == '':
        flash('No photo selected', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    file = request.files['photo']
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    encoding = get_face_encoding(filepath)
    if encoding is None:
        os.remove(filepath)
        flash('Could not find a face in the uploaded image.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    serialized = serialize_encoding(encoding)
    new_person = Person(name=name, person_details=details, image_path=filename, face_encoding=serialized)
    db.session.add(new_person)
    db.session.commit()
    flash('Person added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_person/<int:person_id>')
@admin_required
def delete_person(person_id):
    person = Person.query.get_or_404(person_id)
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], person.image_path))
    except FileNotFoundError:
        pass
    db.session.delete(person)
    db.session.commit()
    flash('Person deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

# --- USER ROUTES ---
@app.route('/sketch')
@login_required
def sketch_constructor():
    parts = {}
    base_path = 'static/sketch_parts'
    for category in os.listdir(base_path):
        cat_path = os.path.join(base_path, category)
        if os.path.isdir(cat_path):
            parts[category] = [f"{category}/{f}" for f in os.listdir(cat_path)]
    return render_template('sketch.html', parts=parts)

@app.route('/recognition', methods=['GET', 'POST'])
@login_required
def recognition():
    results = None
    if request.method == 'POST':
        if 'sketch' not in request.files or request.files['sketch'].filename == '':
            flash('No sketch file provided', 'danger')
            return redirect(request.url)
        
        file = request.files['sketch']
        filename = "temp_sketch_" + secure_filename(file.filename)
        filepath = os.path.join(app.config['SKETCH_UPLOAD_FOLDER'], filename)
        file.save(filepath)

        sketch_encoding = get_face_encoding(filepath)
        if sketch_encoding is None:
            flash('Could not detect a face in the uploaded sketch.', 'warning')
        else:
            results = find_matches(sketch_encoding)
    return render_template('recognition.html', results=results)

# --- PHOTO TO SKETCH ROUTE ---
@app.route('/photo-to-sketch', methods=['GET', 'POST'])
@login_required
def photo_to_sketch():
    sketch_data_url = None
    if request.method == 'POST':
        if 'photo' not in request.files or request.files['photo'].filename == '':
            flash('No photo provided', 'danger')
            return redirect(request.url)
        
        file = request.files['photo']
        
        # Read image bytes directly from the uploaded file
        image_bytes = file.read()

        # Call the in-memory conversion function from utils.py
        sketch_bytes = convert_to_sketch_in_memory(image_bytes)

        if sketch_bytes:
            # Encode the sketch bytes into a Base64 string to create a data URL
            sketch_base64 = base64.b64encode(sketch_bytes).decode('utf-8')
            sketch_data_url = f"data:image/jpeg;base64,{sketch_base64}"
        else:
            flash('Could not convert image to sketch.', 'danger')

    return render_template('photo_to_sketch.html', sketch_data_url=sketch_data_url)


# --- UTILITY ROUTE FOR SERVING FILES ---
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    # This route can serve files from the main database folder
    if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    # It can also serve files from the temporary uploads folder
    elif os.path.exists(os.path.join(app.config['SKETCH_UPLOAD_FOLDER'], filename)):
        return send_from_directory(app.config['SKETCH_UPLOAD_FOLDER'], filename)
    else:
        # Return a 404 error if the file is not found in either directory
        return "File not found.", 404

if __name__ == '__main__':
    # Ensure all necessary upload directories exist when the app starts
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['SKETCH_UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
