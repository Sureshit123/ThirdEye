import os
import base64
import uuid
from functools import wraps
from urllib.parse import quote_plus

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_from_directory,
    jsonify
)

from werkzeug.utils import secure_filename

from models import db, User, Person, bcrypt

from utils import (
    get_face_encoding,
    serialize_encoding,
    find_matches,
    convert_to_sketch_in_memory
)


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

app = Flask(__name__)

# Change this to a strong random secret before production.
app.config["SECRET_KEY"] = "your_super_secret_key_change_this"


# ============================================================
# MYSQL DATABASE CONFIGURATION
# ============================================================

DB_PASSWORD = quote_plus("MyNewPassword@123")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+mysqlconnector://root:{DB_PASSWORD}"
    "@localhost:3306/thirdeye_db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# ============================================================
# UPLOAD FOLDERS
# ============================================================

app.config["UPLOAD_FOLDER"] = "static/person_db"
app.config["SKETCH_UPLOAD_FOLDER"] = "static/uploads"


# ============================================================
# ALLOWED FILE EXTENSIONS
# ============================================================

ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}


# ============================================================
# INITIALIZE EXTENSIONS
# ============================================================

db.init_app(app)
bcrypt.init_app(app)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def ensure_upload_folders():
    """
    Create required upload folders if they do not exist.
    """
    os.makedirs(
        app.config["UPLOAD_FOLDER"],
        exist_ok=True
    )

    os.makedirs(
        app.config["SKETCH_UPLOAD_FOLDER"],
        exist_ok=True
    )


def allowed_file(filename):
    """
    Check whether an uploaded file has an allowed extension.
    """
    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_EXTENSIONS


def make_unique_filename(original_filename, prefix="file"):
    """
    Create a unique filename so that files from different
    test subjects never overwrite each other.
    """

    original_filename = secure_filename(
        original_filename or ""
    )

    extension = os.path.splitext(
        original_filename
    )[1].lower()

    if not extension:
        extension = ".jpg"

    unique_id = uuid.uuid4().hex[:12]

    return f"{prefix}_{unique_id}{extension}"


def make_unique_temp_filename(prefix="temp_sketch"):
    """
    Create a unique temporary filename.
    """
    unique_id = uuid.uuid4().hex[:12]

    return f"{prefix}_{unique_id}.jpg"


def safe_remove(filepath):
    """
    Safely remove a file if it exists.
    """
    if not filepath:
        return

    if not os.path.exists(filepath):
        return

    try:
        os.remove(filepath)
        print(f"[CLEANUP] Removed: {filepath}")

    except Exception as error:
        print(
            f"[CLEANUP ERROR] Could not remove "
            f"{filepath}: {error}"
        )


# ============================================================
# ACCESS CONTROL DECORATORS
# ============================================================

def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please log in to access this page.",
                "danger"
            )

            return redirect(
                url_for("login")
            )

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if (
            "user_id" not in session
            or session.get("role") != "admin"
        ):

            flash(
                "You do not have permission to access this page.",
                "danger"
            )

            return redirect(
                url_for("home")
            )

        return f(*args, **kwargs)

    return decorated_function


# ============================================================
# DATABASE INITIALIZATION COMMAND
# ============================================================

@app.cli.command("init-db")
def init_db_command():
    """
    Create database tables and the default admin user.
    """

    with app.app_context():

        try:

            db.create_all()

            admin_user = User.query.filter_by(
                username="admin"
            ).first()

            if not admin_user:

                admin_user = User(
                    username="admin",
                    password="password123",
                    role="admin"
                )

                db.session.add(admin_user)

                db.session.commit()

                print(
                    "Initialized the database and created "
                    "admin user (admin/password123)."
                )

            else:

                print(
                    "Database initialized. "
                    "Admin user already exists."
                )

        except Exception as error:

            db.session.rollback()

            print(
                f"[INIT DB ERROR] {error}"
            )

            raise


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template(
        "home.html"
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if not username or not password:

            flash(
                "Username and password are required.",
                "danger"
            )

            return render_template(
                "login.html"
            )

        user = User.query.filter_by(
            username=username
        ).first()

        if user and user.check_password(password):

            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role

            flash(
                f"Welcome, {user.username}!",
                "success"
            )

            if user.role == "admin":

                return redirect(
                    url_for("admin_dashboard")
                )

            return redirect(
                url_for("sketch_constructor")
            )

        flash(
            "Invalid username or password.",
            "danger"
        )

    return render_template(
        "login.html"
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if not username or not password:

            flash(
                "Username and password are required.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        existing_user = User.query.filter_by(
            username=username
        ).first()

        if existing_user:

            flash(
                "Username already exists. "
                "Please choose a different one.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        try:

            new_user = User(
                username=username,
                password=password,
                role="user"
            )

            db.session.add(new_user)
            db.session.commit()

            flash(
                "Account created successfully! "
                "You can now log in.",
                "success"
            )

            return redirect(
                url_for("login")
            )

        except Exception as error:

            db.session.rollback()

            print(
                f"[REGISTER ERROR] {error}"
            )

            flash(
                "Could not create the account.",
                "danger"
            )

    return render_template(
        "register.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "info"
    )

    return redirect(
        url_for("home")
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    persons = Person.query.order_by(
        Person.id.desc()
    ).all()

    return render_template(
        "admin_dashboard.html",
        persons=persons
    )


# ============================================================
# ADD TEST SUBJECT
# ============================================================

@app.route(
    "/admin/add_person",
    methods=["POST"]
)
@admin_required
def add_person():

    ensure_upload_folders()

    name = request.form.get(
        "name",
        ""
    ).strip()

    details = request.form.get(
        "person_details",
        ""
    ).strip()

    # --------------------------------------------------------
    # Validate name
    # --------------------------------------------------------

    if not name:

        flash(
            "Name is required.",
            "danger"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    # --------------------------------------------------------
    # Validate photo field
    # --------------------------------------------------------

    if "photo" not in request.files:

        flash(
            "No photo was uploaded.",
            "danger"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    file = request.files["photo"]

    if not file or not file.filename:

        flash(
            "No photo selected.",
            "danger"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    original_filename = secure_filename(
        file.filename
    )

    if not original_filename:

        flash(
            "Invalid photo filename.",
            "danger"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    # --------------------------------------------------------
    # Validate extension
    # --------------------------------------------------------

    if not allowed_file(original_filename):

        flash(
            "Invalid image format. "
            "Use JPG, JPEG, PNG or WEBP.",
            "danger"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    # --------------------------------------------------------
    # Create UNIQUE photo filename
    # --------------------------------------------------------

    filename = make_unique_filename(
        original_filename,
        prefix="person"
    )

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    sketch_filepath = None

    try:

        # ====================================================
        # SAVE ORIGINAL PHOTO
        # ====================================================

        file.save(filepath)

        print(
            "================================================"
        )

        print(
            f"[ADD PERSON] Name: {name}"
        )

        print(
            f"[ADD PERSON] Photo saved: {filepath}"
        )

        # ====================================================
        # GENERATE PHOTO FACE ENCODING
        # ====================================================

        photo_encoding = get_face_encoding(
            filepath
        )

        if photo_encoding is None:

            raise ValueError(
                "Could not detect a face in the uploaded photo."
            )

        print(
            "[ADD PERSON] Photo face encoding generated."
        )

        # ====================================================
        # READ ORIGINAL PHOTO
        # ====================================================

        with open(
            filepath,
            "rb"
        ) as image_file:

            image_bytes = image_file.read()

        if not image_bytes:

            raise ValueError(
                "Uploaded image is empty."
            )

        # ====================================================
        # GENERATE REFERENCE SKETCH
        # ====================================================

        sketch_bytes = convert_to_sketch_in_memory(
            image_bytes
        )

        if not sketch_bytes:

            raise ValueError(
                "Could not generate a sketch from the uploaded photo."
            )

        print(
            "[ADD PERSON] Reference sketch generated."
        )

        # ====================================================
        # UNIQUE REFERENCE SKETCH NAME
        # ====================================================

        base_name = os.path.splitext(
            filename
        )[0]

        sketch_filename = (
            f"{base_name}_sketch.jpg"
        )

        sketch_filepath = os.path.join(
            app.config["SKETCH_UPLOAD_FOLDER"],
            sketch_filename
        )

        # ====================================================
        # SAVE REFERENCE SKETCH
        # ====================================================

        with open(
            sketch_filepath,
            "wb"
        ) as sketch_file:

            sketch_file.write(
                sketch_bytes
            )

        print(
            f"[ADD PERSON] Sketch saved: {sketch_filepath}"
        )

        # ====================================================
        # GENERATE SKETCH ENCODING
        # ====================================================

        sketch_encoding = get_face_encoding(
            sketch_filepath
        )

        if sketch_encoding is None:

            raise ValueError(
                "Could not generate a face encoding "
                "from the reference sketch."
            )

        print(
            "[ADD PERSON] Sketch face encoding generated."
        )

        # ====================================================
        # SERIALIZE PHOTO ENCODING
        # ====================================================

        photo_serialized = serialize_encoding(
            photo_encoding
        )

        if not photo_serialized:

            raise ValueError(
                "Photo encoding serialization failed."
            )

        # ====================================================
        # SERIALIZE SKETCH ENCODING
        # ====================================================

        sketch_serialized = serialize_encoding(
            sketch_encoding
        )

        if not sketch_serialized:

            raise ValueError(
                "Sketch encoding serialization failed."
            )

        # ====================================================
        # CREATE DATABASE RECORD
        # ====================================================

        new_person = Person(
            name=name,
            person_details=details,
            image_path=filename,
            face_encoding=photo_serialized,
            sketch_path=sketch_filename,
            sketch_encoding=sketch_serialized
        )

        db.session.add(
            new_person
        )

        db.session.commit()

        print(
            f"[ADD PERSON] Database record created."
        )

        print(
            f"[ADD PERSON] Database ID: {new_person.id}"
        )

        print(
            f"[ADD PERSON] Photo: {filename}"
        )

        print(
            f"[ADD PERSON] Sketch: {sketch_filename}"
        )

        print(
            "================================================"
        )

        flash(
            "Test subject added successfully with "
            "reference photo and sketch.",
            "success"
        )

    except Exception as error:

        print(
            "================================================"
        )

        print(
            f"[ADD PERSON ERROR] {error}"
        )

        print(
            "================================================"
        )

        # ----------------------------------------------------
        # Rollback DB
        # ----------------------------------------------------

        db.session.rollback()

        # ----------------------------------------------------
        # Remove photo
        # ----------------------------------------------------

        safe_remove(
            filepath
        )

        # ----------------------------------------------------
        # Remove sketch
        # ----------------------------------------------------

        safe_remove(
            sketch_filepath
        )

        flash(
            f"Could not add test subject: {error}",
            "danger"
        )

    return redirect(
        url_for("admin_dashboard")
    )


# ============================================================
# DELETE TEST SUBJECT
# ============================================================

@app.route(
    "/admin/delete_person/<int:person_id>"
)
@admin_required
def delete_person(person_id):

    person = Person.query.get_or_404(
        person_id
    )

    image_path = None
    sketch_path = None

    try:

        # ----------------------------------------------------
        # Remember physical file paths
        # ----------------------------------------------------

        if person.image_path:

            image_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                person.image_path
            )

        if person.sketch_path:

            sketch_path = os.path.join(
                app.config["SKETCH_UPLOAD_FOLDER"],
                person.sketch_path
            )

        # ----------------------------------------------------
        # Delete database record
        # ----------------------------------------------------

        db.session.delete(
            person
        )

        db.session.commit()

        # ----------------------------------------------------
        # Delete photo
        # ----------------------------------------------------

        safe_remove(
            image_path
        )

        # ----------------------------------------------------
        # Delete sketch
        # ----------------------------------------------------

        safe_remove(
            sketch_path
        )

        flash(
            "Test subject deleted successfully.",
            "success"
        )

    except Exception as error:

        db.session.rollback()

        print(
            f"[DELETE PERSON ERROR] {error}"
        )

        flash(
            "Could not delete test subject.",
            "danger"
        )

    return redirect(
        url_for("admin_dashboard")
    )


# ============================================================
# SKETCH CONSTRUCTOR
# ============================================================

@app.route("/sketch")
@login_required
def sketch_constructor():

    parts = {}

    base_path = "static/sketch_parts"

    if os.path.exists(base_path):

        for category in os.listdir(base_path):

            category_path = os.path.join(
                base_path,
                category
            )

            if not os.path.isdir(category_path):
                continue

            parts[category] = []

            for filename in os.listdir(
                category_path
            ):

                file_path = os.path.join(
                    category_path,
                    filename
                )

                if os.path.isfile(file_path):

                    parts[category].append(
                        f"{category}/{filename}"
                    )

    return render_template(
        "sketch.html",
        parts=parts
    )


# ============================================================
# FACE SKETCH RECOGNITION
# ============================================================

@app.route(
    "/recognition",
    methods=["GET", "POST"]
)
@login_required
def recognition():

    results = None

    if request.method == "POST":

        filepath = None

        try:

            ensure_upload_folders()

            # ==================================================
            # OPTION 1
            # DIRECT SKETCH FILE UPLOAD
            # ==================================================

            if (
                "sketch" in request.files
                and request.files["sketch"].filename
            ):

                file = request.files["sketch"]

                original_filename = secure_filename(
                    file.filename
                )

                if not original_filename:

                    flash(
                        "Invalid sketch filename.",
                        "danger"
                    )

                    return redirect(
                        request.url
                    )

                # ------------------------------------------------
                # Validate sketch format
                # ------------------------------------------------

                if not allowed_file(
                    original_filename
                ):

                    flash(
                        "Invalid sketch format. "
                        "Use JPG, JPEG, PNG or WEBP.",
                        "danger"
                    )

                    return redirect(
                        request.url
                    )

                # ------------------------------------------------
                # IMPORTANT:
                # UNIQUE temporary filename
                # ------------------------------------------------

                filename = make_unique_filename(
                    original_filename,
                    prefix="temp_sketch"
                )

                filepath = os.path.join(
                    app.config["SKETCH_UPLOAD_FOLDER"],
                    filename
                )

                file.save(
                    filepath
                )

                print(
                    f"[RECOGNITION] Uploaded sketch: "
                    f"{filepath}"
                )

            # ==================================================
            # OPTION 2
            # GENERATED SKETCH DATA URL
            # ==================================================

            elif request.form.get(
                "sketch_data_url"
            ):

                sketch_data_url = request.form.get(
                    "sketch_data_url"
                )

                # ------------------------------------------------
                # Validate Data URL
                # ------------------------------------------------

                if not sketch_data_url.startswith(
                    "data:image/"
                ):

                    flash(
                        "Invalid generated sketch data.",
                        "danger"
                    )

                    return redirect(
                        url_for("photo_to_sketch")
                    )

                # ------------------------------------------------
                # Decode Base64
                # ------------------------------------------------

                try:

                    header, encoded = (
                        sketch_data_url.split(
                            ",",
                            1
                        )
                    )

                    sketch_bytes = base64.b64decode(
                        encoded,
                        validate=True
                    )

                except Exception as decode_error:

                    print(
                        f"[RECOGNITION] "
                        f"Base64 decode error: "
                        f"{decode_error}"
                    )

                    flash(
                        "Could not decode the generated sketch.",
                        "danger"
                    )

                    return redirect(
                        url_for("photo_to_sketch")
                    )

                if not sketch_bytes:

                    flash(
                        "Generated sketch is empty.",
                        "danger"
                    )

                    return redirect(
                        url_for("photo_to_sketch")
                    )

                # ------------------------------------------------
                # IMPORTANT:
                # UNIQUE generated filename
                # ------------------------------------------------

                filename = make_unique_temp_filename(
                    prefix="generated_sketch"
                )

                filepath = os.path.join(
                    app.config["SKETCH_UPLOAD_FOLDER"],
                    filename
                )

                with open(
                    filepath,
                    "wb"
                ) as output_file:

                    output_file.write(
                        sketch_bytes
                    )

                print(
                    f"[RECOGNITION] Generated sketch saved: "
                    f"{filepath}"
                )

            # ==================================================
            # NO SKETCH
            # ==================================================

            else:

                flash(
                    "No sketch file provided.",
                    "danger"
                )

                return redirect(
                    request.url
                )

            # ==================================================
            # VALIDATE FILE EXISTS
            # ==================================================

            if not filepath or not os.path.exists(
                filepath
            ):

                flash(
                    "Sketch file could not be saved.",
                    "danger"
                )

                return redirect(
                    request.url
                )

            # ==================================================
            # IMPORTANT:
            # DO NOT CONVERT THE SKETCH AGAIN
            #
            # The supplied file is already a sketch.
            # We directly generate its face encoding.
            # ==================================================

            print(
                "------------------------------------------------"
            )

            print(
                "[RECOGNITION] Generating query sketch encoding..."
            )

            sketch_encoding = get_face_encoding(
                filepath
            )

            if sketch_encoding is None:

                print(
                    "[RECOGNITION] "
                    "No face detected in query sketch."
                )

                flash(
                    "Could not detect a face in the sketch. "
                    "Try a clearer face image.",
                    "warning"
                )

            else:

                print(
                    "[RECOGNITION] Sketch encoding generated."
                )

                print(
                    f"[RECOGNITION] Encoding shape: "
                    f"{getattr(sketch_encoding, 'shape', None)}"
                )

                print(
                    f"[RECOGNITION] Encoding dtype: "
                    f"{getattr(sketch_encoding, 'dtype', None)}"
                )

                # ==================================================
                # MATCH AGAINST STORED SKETCH ENCODINGS
                # ==================================================

                results = find_matches(
                    sketch_encoding,
                    top_n=5
                )

                if not results:

                    flash(
                        "No sufficiently similar test "
                        "subjects were found.",
                        "info"
                    )

                else:

                    print(
                        f"[RECOGNITION] "
                        f"{len(results)} result(s) returned."
                    )

            print(
                "------------------------------------------------"
            )

        except Exception as error:

            print(
                "================================================"
            )

            print(
                f"[RECOGNITION ERROR] {error}"
            )

            print(
                "================================================"
            )

            flash(
                "An error occurred during analysis.",
                "danger"
            )

        finally:

            # ==================================================
            # DELETE ONLY THE QUERY/TEMPORARY SKETCH
            #
            # This will NEVER delete reference sketches because
            # filepath here belongs only to the recognition
            # request.
            # ==================================================

            if filepath:

                safe_remove(
                    filepath
                )

    return render_template(
        "recognition.html",
        results=results
    )


# ============================================================
# PHOTO TO SKETCH
# ============================================================

@app.route(
    "/photo-to-sketch",
    methods=["GET", "POST"]
)
@login_required
def photo_to_sketch():

    sketch_data_url = None

    if request.method == "POST":

        # ----------------------------------------------------
        # Validate upload
        # ----------------------------------------------------

        if "photo" not in request.files:

            flash(
                "No photo provided.",
                "danger"
            )

            return redirect(
                request.url
            )

        file = request.files["photo"]

        if not file or not file.filename:

            flash(
                "No photo selected.",
                "danger"
            )

            return redirect(
                request.url
            )

        original_filename = secure_filename(
            file.filename
        )

        if not allowed_file(
            original_filename
        ):

            flash(
                "Invalid image format. "
                "Use JPG, JPEG, PNG or WEBP.",
                "danger"
            )

            return redirect(
                request.url
            )

        # ----------------------------------------------------
        # Read image
        # ----------------------------------------------------

        image_bytes = file.read()

        if not image_bytes:

            flash(
                "Uploaded photo is empty.",
                "danger"
            )

            return redirect(
                request.url
            )

        try:

            # ==================================================
            # PHOTO -> SKETCH
            # ==================================================

            sketch_bytes = convert_to_sketch_in_memory(
                image_bytes
            )

            if not sketch_bytes:

                flash(
                    "Could not convert image to sketch.",
                    "danger"
                )

            else:

                # ==================================================
                # SKETCH -> BASE64
                # ==================================================

                sketch_base64 = base64.b64encode(
                    sketch_bytes
                ).decode("utf-8")

                sketch_data_url = (
                    "data:image/jpeg;base64,"
                    + sketch_base64
                )

                print(
                    "[PHOTO TO SKETCH] "
                    "Sketch generated successfully."
                )

        except Exception as error:

            print(
                f"[PHOTO TO SKETCH ERROR] {error}"
            )

            flash(
                "An error occurred while converting "
                "the image to a sketch.",
                "danger"
            )

    return render_template(
        "photo_to_sketch.html",
        sketch_data_url=sketch_data_url
    )


# ============================================================
# LIVE RECOGNITION PAGE
# ============================================================

@app.route("/live-recognition")
@login_required
def live_recognition():

    return render_template(
        "live_recognition.html"
    )


# ============================================================
# LIVE SKETCH GENERATION
# ============================================================

@app.route(
    "/live-sketch",
    methods=["POST"]
)
@login_required
def live_sketch():

    try:

        # ==================================================
        # VALIDATE CAMERA FRAME
        # ==================================================

        if "photo" not in request.files:

            return jsonify({
                "success": False,
                "message": (
                    "No camera frame was received."
                )
            }), 400

        file = request.files["photo"]

        if not file or not file.filename:

            return jsonify({
                "success": False,
                "message": (
                    "No camera frame was received."
                )
            }), 400

        # ==================================================
        # READ CAMERA IMAGE
        # ==================================================

        image_bytes = file.read()

        if not image_bytes:

            return jsonify({
                "success": False,
                "message": (
                    "The captured frame is empty."
                )
            }), 400

        # ==================================================
        # CAMERA PHOTO -> SKETCH
        # ==================================================

        sketch_bytes = convert_to_sketch_in_memory(
            image_bytes
        )

        if not sketch_bytes:

            return jsonify({
                "success": False,
                "message": (
                    "No face could be detected. "
                    "Move closer to the camera, "
                    "face the camera directly, "
                    "and try again."
                )
            }), 422

        # ==================================================
        # SKETCH -> BASE64
        # ==================================================

        sketch_base64 = base64.b64encode(
            sketch_bytes
        ).decode("utf-8")

        return jsonify({
            "success": True,
            "sketch_data_url": (
                "data:image/jpeg;base64,"
                + sketch_base64
            ),
            "message": (
                "Face sketch generated successfully."
            )
        })

    except Exception as error:

        print(
            "================================================"
        )

        print(
            f"[LIVE SKETCH ERROR] {error}"
        )

        print(
            "================================================"
        )

        return jsonify({
            "success": False,
            "message": (
                "An error occurred while generating "
                "the sketch."
            )
        }), 500


# ============================================================
# SERVE UPLOADED FILES
# ============================================================

@app.route(
    "/uploads/<path:filename>"
)
def uploaded_file(filename):

    # ==================================================
    # CHECK PERSON PHOTO FOLDER
    # ==================================================

    main_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    if os.path.isfile(main_path):

        return send_from_directory(
            app.config["UPLOAD_FOLDER"],
            filename
        )

    # ==================================================
    # CHECK SKETCH FOLDER
    # ==================================================

    sketch_path = os.path.join(
        app.config["SKETCH_UPLOAD_FOLDER"],
        filename
    )

    if os.path.isfile(sketch_path):

        return send_from_directory(
            app.config["SKETCH_UPLOAD_FOLDER"],
            filename
        )

    return (
        "File not found.",
        404
    )


# ============================================================
# APPLICATION STARTUP
# ============================================================

ensure_upload_folders()


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    print(
        "================================================"
    )

    print(
        "Forensic Face Sketch Demo Application"
    )

    print(
        "Database: thirdeye_db"
    )

    print(
        f"Photo folder: "
        f"{app.config['UPLOAD_FOLDER']}"
    )

    print(
        f"Sketch folder: "
        f"{app.config['SKETCH_UPLOAD_FOLDER']}"
    )

    print(
        "================================================"
    )

    app.run(
        debug=True
    )