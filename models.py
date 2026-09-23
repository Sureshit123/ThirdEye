from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(200),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        nullable=False,
        default='user'
    )

    def __init__(
        self,
        username,
        password,
        role='user'
    ):
        self.username = username

        self.password = (
            bcrypt
            .generate_password_hash(password)
            .decode('utf-8')
        )

        self.role = role

    def check_password(self, password):
        return bcrypt.check_password_hash(
            self.password,
            password
        )


class Person(db.Model):
    __tablename__ = 'persons'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    person_details = db.Column(
        db.Text,
        nullable=True
    )

    # Original/reference photograph
    image_path = db.Column(
        db.String(200),
        nullable=False
    )

    # Encoding generated from reference photograph
    face_encoding = db.Column(
        db.Text,
        nullable=False
    )

    # -----------------------------------------
    # Reference sketch
    # -----------------------------------------

    sketch_path = db.Column(
        db.String(200),
        nullable=True
    )

    # Encoding generated from reference sketch
    sketch_encoding = db.Column(
        db.Text,
        nullable=True
    )