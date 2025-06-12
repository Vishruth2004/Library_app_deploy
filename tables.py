from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import desc, and_, or_

db=SQLAlchemy()

class User(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  username = db.Column(db.String(80), unique=True)
  password = db.Column(db.String(256))
  role = db.Column(db.String(20), default='user')

class LibrarianRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')

class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    books = db.relationship('Book', backref='section', lazy='dynamic')

    def __repr__(self):
        return f'<Section {self.name}>'

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text)
    author = db.Column(db.String(100))
    date_issued = db.Column(db.DateTime)
    return_date = db.Column(db.DateTime)
    section_id = db.Column(db.Integer, db.ForeignKey('section.id'), nullable=False)

    def __repr__(self):
        return f'<Book {self.name}>'

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    user = db.relationship('User', backref='cart_items')
    book = db.relationship('Book', backref='in_carts')

class BookRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    librarian_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    date_requested = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Pending Approval')
    rejection_reason = db.Column(db.String(255), default=None)

    user = db.relationship('User', foreign_keys=[user_id], backref='book_requests')
    librarian = db.relationship('User', foreign_keys=[librarian_id], backref='approved_requests', lazy='joined')
    book = db.relationship('Book', backref='requests')

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(20), nullable=False)
    book_name = db.Column(db.String(80), nullable=False)
    rating = db.Column(db.Integer)
    comment = db.Column(db.Text)
    date_given = db.Column(db.DateTime, default=datetime.utcnow)
