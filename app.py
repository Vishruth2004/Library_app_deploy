from flask import Flask, redirect, request, render_template, session, url_for, send_from_directory, flash, get_flashed_messages
from tables import *
from datetime import datetime, timedelta
from flask_migrate import Migrate
import os
from os.path import join

app = Flask(__name__)

app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'Hello_My_Secert_Key')

database_url = os.environ.get('DATABASE_URL', '')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
if not database_url:
    static_folder = os.path.abspath('static')
    database_file = join(static_folder, 'test.db')
    database_url = f'sqlite:///{database_file}'
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

upload_folder = 'static/uploads/' 
app.config['UPLOAD_FOLDER'] = upload_folder 

db.init_app(app)
app.app_context().push()
migrate = Migrate(app, db)

#--------------------------------------------------Intial Pages---------------------------------------------------#

@app.route('/')
def index():
  return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error_message = None
    admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')

    if request.method == 'POST':
        name = request.form['username']
        user_password = request.form['password']

        # Check if it's an admin login
        if name == admin_username and user_password == admin_password:
            session['admin_id'] = 1
            session['role'] = 'admin'
            return redirect('/admin/dashboard')

        # Check for regular user login
        user = User.query.filter_by(username=name).first()
        librarian_person = LibrarianRequest.query.filter_by(username=name).first()
    
        if not user:
            error_message = "Username is incorrect"
            if librarian_person:
                if librarian_person.status == 'pending':
                    error_message = "Your Request is Pending for Approval"
                elif librarian_person.status == 'rejected':
                    db.session.delete(librarian_person)
                    db.session.commit()
                    error_message = "Your Request for Aceess is Denined"

        elif user.password != user_password:
            error_message = "Password is incorrect"
        else:
            if user.role == 'user':
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = 'user'
                return redirect('/user')
            elif user.role == 'librarian':
                session['librarian_id'] = user.id
                session['librarian_name'] = user.username
                session['role'] = 'librarian'
                librarian_person = User.query.filter_by(username=user.username).first()
                return redirect('/librarian')

    return render_template('login.html', error_message=error_message)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error_message = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        # Check if the username already exists
        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            error_message = "Username already exists. Please choose a different username."
        else:
            if role == 'librarian':
                new_request = LibrarianRequest(username=username, password=password)
                db.session.add(new_request)
                db.session.commit()
                return redirect(url_for('librarian_registration_success'))

            if role == 'user':
                new_user = User(username=username, password=password, role=role)
                db.session.add(new_user)
                db.session.commit()
                flash('Registration successful. You can now log in.', 'success')
                return redirect('/login')

    return render_template('register.html', error_message=error_message)

@app.route('/librarian_registration_success')
def librarian_registration_success():
    return render_template('librarian_registration_success.html')

#---------------------------------------------------- Admin ---------------------------------------------------#

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session or session['admin_id'] is None:
        return redirect('/login')

    requests = LibrarianRequest.query.all()
    logged_in_users = User.query.all()
    
    return render_template('admin_dashboard.html', requests=requests, logged_in_users=logged_in_users)

@app.route('/admin/accept_librarian/<int:id>')
def accept_librarian(id):
    librarian_request = LibrarianRequest.query.get(id)

    if librarian_request:
        new_librarian = User(username=librarian_request.username, password=librarian_request.password, role='librarian')
        db.session.add(new_librarian)
        db.session.commit()

        librarian_request.status = 'approved'
        db.session.commit()
        flash('Librarian has been approved.', 'success')

    return redirect('/admin/dashboard')

@app.route('/admin/reject_librarian/<int:id>')
def reject_librarian(id):
    librarian_request = LibrarianRequest.query.get(id)

    if librarian_request:
        librarian_request.status = 'rejected'
        db.session.commit()
        flash('Librarian request has been rejected.', 'success')

    return redirect('/admin/dashboard')

@app.route('/admin/disable_user/<int:user_id>', endpoint='disable_user')
def disable_user(user_id):
    user_entry = User.query.get(user_id)
    library = LibrarianRequest.query.filter_by(username=user_entry.username).first()

    if user_entry:
        db.session.delete(user_entry)
        db.session.commit()
        flash('User has been disabled.', 'success')

    if library:
        db.session.delete(library)
        db.session.commit()
        flash('Librarian has been disabled.', 'success')

    return redirect('/admin/dashboard')
   
#----------------------------------------------- Librarian Pages ---------------------------------------------------#

@app.route('/librarian', methods=['GET', 'POST'])
def librarian_dashboard():
    sections = Section.query.order_by(desc(Section.date_created)).all()
    librarian_name = session.get('librarian_name', 'Guest Librarian')
    search_query = request.args.get('q', '')

    if request.method == 'POST':
        search_query = request.form.get('q')
        search_type = request.form['search-type']
        search_by = request.form['search-by']

        if search_query:
            results = search_sections(search_query, search_by, search_type)
            return render_template('search_results.html', results=results, search_query=search_query, search_type=search_type)

    return render_template('librarian_dashboard.html', sections=sections, librarian_name=librarian_name)

@app.route('/section/<int:section_id>', methods=['GET'])
def section_details(section_id):
    section = Section.query.get_or_404(section_id)
    books = section.books.order_by(desc(Book.id)).all()
    return render_template('section_details.html', section=section, books=books)

#------------------------------------------------ CRUD Sections ---------------------------------------------------#

@app.route('/add-section', methods=['GET', 'POST'])
def add_section():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        date_created_str = request.form['date_created']

        date_created = datetime.strptime(date_created_str, '%Y-%m-%dT%H:%M')

        new_section = Section(name=name, description=description, date_created=date_created)
        db.session.add(new_section)
        db.session.commit()
        flash('Section has been added successfully.', 'success')
        return redirect(url_for('librarian_dashboard'))
    return render_template('add_section.html')

@app.route('/update-section/<int:section_id>', methods=['GET', 'POST'])
def update_section(section_id):
    section = Section.query.get_or_404(section_id)

    if request.method == 'POST':
        section.name = request.form['name']
        section.description = request.form['description']
        date_created_str = request.form['date_created']

        section.date_created = datetime.strptime(date_created_str, '%Y-%m-%dT%H:%M')

        db.session.commit()
        flash('Section has been updated successfully.', 'success')
        return redirect(url_for('librarian_dashboard'))

    return render_template('update_section.html', section=section)

@app.route('/delete-section/<int:section_id>')
def delete_section(section_id):
    section = Section.query.get_or_404(section_id)
    books = Book.query.filter_by(section_id=section_id).all()
    
    for booku in books:
        # Delete the book
        book_id = booku.id
        carts_with_book = Cart.query.filter_by(book_id=book_id).all()
        for cart in carts_with_book:
            db.session.delete(cart)

        if book_id:
            book = Book.query.get_or_404(book_id)
            book_requests = BookRequest.query.filter_by(book_id=book_id).all()
            for book_request in book_requests:
                db.session.delete(book_request)
            db.session.delete(book)

    db.session.delete(section)
    db.session.commit()
    flash('Section has been deleted successfully.', 'success')

    return redirect(url_for('librarian_dashboard'))
   
#------------------------------------------------- CRUD Books ---------------------------------------------------#

@app.route('/add-book/<int:section_id>', methods=['GET', 'POST'])
def add_book(section_id):
    section = Section.query.get_or_404(section_id)
    if request.method == 'POST':
        name = request.form['name']
        content_type = request.form['content_type']
        author = request.form['author']

        if content_type == 'text':
            content = request.form['text_content']
            new_book = Book(name=name, content=content, author=author, section=section)
        elif content_type == 'pdf':
            file = request.files.get('file')
            if file and file.filename.endswith('.pdf'):
                file.save(app.config['UPLOAD_FOLDER'] + file.filename)
                content = app.config['UPLOAD_FOLDER'] + file.filename
                new_book = Book(name=name, content=content, author=author, section=section)
            else:
                # Handle invalid file upload
                flash('Invalid File Upload. Use PDF File.', 'danger')
                return render_template('add_book.html', section_id=section_id)

        db.session.add(new_book)
        db.session.commit()
        flash('Book has been added successfully.', 'success')
        return redirect(url_for('section_details', section_id=section_id))

    return render_template('add_book.html', section_id=section_id)

@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/update-book/<int:book_id>', methods=['GET', 'POST'])
def update_book(book_id):
    book = Book.query.get_or_404(book_id)

    if request.method == 'POST':
        name = request.form['name']
        content_type = request.form['content_type']
        author = request.form['author']

        if content_type == 'text':
            content = request.form['text_content']
            book.name = name
            book.content = content
            book.author = author
        elif content_type == 'pdf':
            file = request.files.get('file')
            if file and file.filename.endswith('.pdf'):
                file.save(app.config['UPLOAD_FOLDER'] + file.filename)
                book.name = name
                book.content = app.config['UPLOAD_FOLDER'] + file.filename
                book.author = author
            else:
                # Handle invalid file upload
                flash('Invalid File Upload. Use PDF File.', 'danger')
                return render_template('update_book.html', book=book)
            
        db.session.commit()
        flash('Book has been updated successfully.', 'success')
        return redirect(url_for('section_details', section_id=book.section.id))

    return render_template('update_book.html', book=book)

@app.route('/delete-book/<int:book_id>')
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)

    carts_with_book = Cart.query.filter_by(book_id=book_id).all()
    for cart in carts_with_book:
        db.session.delete(cart)
    
    book_requests = BookRequest.query.filter_by(book_id=book_id).all()
    
    for book_request in book_requests:
        db.session.delete(book_request)
    
    section_id = book.section.id  # Store the section ID before deletion
    
    db.session.delete(book)
    db.session.commit()
    flash('Book has been deleted successfully.', 'success')
    return redirect(url_for('section_details', section_id=section_id))

#----------------------------------- Librarian Book Request & Book Reject Reason ---------------------------------------------------#

@app.route('/librarian/book-requests')
def librarian_book_requests():
    if 'librarian_id' not in session:
        return redirect('/login')

    librarian = User.query.get_or_404(session['librarian_id'])
    pending_requests = BookRequest.query.filter(BookRequest.status == 'Pending Approval').order_by(BookRequest.date_requested.desc()).all()
    return render_template('librarian_book_requests.html', librarian=librarian, pending_requests=pending_requests)

@app.route('/librarian/show-book-requests')
def librarian_show_book_requests():
    if 'librarian_id' not in session:
        return redirect('/login')

    librarian_requests = BookRequest.query.all()
    return render_template('librarian_show_book_requests.html', librarian_requests=librarian_requests)

@app.route('/librarian/accept-request/<int:request_id>')
def librarian_accept_request(request_id):
    book_request = BookRequest.query.get_or_404(request_id)

    book_request.status = 'Approved'
    book_request.librarian_id = session.get('librarian_id')
    book_request.book.date_issued = datetime.utcnow()
    book_request.book.return_date = book_request.book.date_issued + timedelta(days=7)

    db.session.commit()
    flash('Book request has been approved.', 'success')

    return redirect(url_for('librarian_book_requests'))

@app.route('/librarian/reject-request/<int:request_id>')
def librarian_reject_request(request_id):
    book_request = BookRequest.query.get_or_404(request_id)

    book_request.status = 'Rejected'
    book_request.librarian_id = session.get('librarian_id')

    db.session.commit()

    return redirect(url_for('librarian_reject_request_with_reason', request_id=request_id))

@app.route('/librarian/revoke-access/<int:request_id>')
def librarian_revoke_access(request_id):
    book_request = BookRequest.query.get_or_404(request_id)

    book_request.status = 'Access Removed'

    db.session.commit()

    return redirect(url_for('librarian_reject_request_with_reason', request_id=request_id))

@app.route('/librarian/reject-request-with-reason/<int:request_id>', methods=['GET', 'POST'])
def librarian_reject_request_with_reason(request_id):
    book_request = BookRequest.query.get_or_404(request_id)

    if request.method == 'POST':
        rejection_reason = request.form.get('rejection_reason', '')
        book_request.rejection_reason = rejection_reason
        db.session.commit()
        if book_request.status == 'Rejected':
            flash('Book request has been rejected.', 'success')
            return redirect(url_for('librarian_book_requests'))

        if book_request.status == 'Access Removed':
            flash('Access to the book has been revoked.', 'success')
            return redirect(url_for('librarian_show_book_requests'))


    return render_template('librarian_reject_reason.html', request_id=request_id)

@app.route('/librarian/view-rejection-reason/<int:request_id>')
def view_rejection_reason(request_id):
    book_request = BookRequest.query.get_or_404(request_id)
    return render_template('librarian_view_rejection_reason.html', reason=book_request, GoBack = 0)
   
#--------------------------------------------------- User pages ---------------------------------------------------#

@app.route('/user', methods=['GET', 'POST'])
def user_dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get(session['user_id'])

    if user.role != 'user':
        return redirect('/login')
    
    due()
    sections = Section.query.order_by(desc(Section.date_created)).all()
    user_name = session.get('username', 'Guest User')
    search_query = request.args.get('q', '')

    if request.method == 'POST':
        search_query = request.form.get('q')
        search_type = request.form['search-type']
        search_by = request.form['search-by']

        if search_query:
            results = search_sections(search_query, search_by, search_type)
            return render_template('user_search_results.html', results=results, search_query=search_query, search_type=search_type, search_by=search_by)

    return render_template('user_dashboard.html', sections=sections, user_name=user_name)

def due():
    # Get all approved books
    overdue_requests = BookRequest.query.filter(BookRequest.status == 'Approved').all()

    for request in overdue_requests:
        if request.book.return_date < datetime.utcnow():
            # Revoke access for overdue books
            request.status = 'Due Date Passed'
            db.session.commit()

@app.route('/user/section/<int:section_id>', methods=['GET'])
def user_section_details(section_id):
    section = Section.query.get_or_404(section_id)
    books = section.books.order_by(desc(Book.id)).all()
    return render_template('user_section_details.html', section=section, books=books)
   
#------------------------------------------------------ Cart ---------------------------------------------------#

@app.route('/user/cart')
def cart():
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get_or_404(session['user_id'])
    return render_template('cart.html', user=user)

@app.route('/user/add-to-cart/<int:book_id>')
def user_add_to_cart(book_id):
    book = Book.query.get_or_404(book_id)
    user = User.query.get_or_404(session['user_id'])

    if book not in user.cart_items:
        cart_item = Cart(user=user, book=book)
        db.session.add(cart_item)
        db.session.commit()
        flash('Book has been added to your cart.', 'success')

    return redirect(url_for('user_section_details', section_id=book.section.id))

@app.route('/user/search-add-to-cart/<int:book_id>')
def search_user_add_to_cart(book_id):
    book = Book.query.get_or_404(book_id)
    user = User.query.get_or_404(session['user_id'])

    search_query = request.args.get('search_query')
    search_by = request.args.get('search_by')
    search_type = request.args.get('search_type')

    if book not in user.cart_items:
        cart_item = Cart(user=user, book=book)
        db.session.add(cart_item)
        db.session.commit()
        flash('Book has been added to your cart.', 'success')
    results = search_sections(search_query, search_by, search_type)
    return render_template('user_search_results.html', results=results, search_query=search_query, search_type=search_type, search_by=search_by)

@app.route('/user/remove-from-cart/<int:cart_item_id>')
def user_remove_from_cart(cart_item_id):
    cart_item = Cart.query.get_or_404(cart_item_id)
    
    db.session.delete(cart_item)
    db.session.commit()

    return redirect(url_for('cart'))

#--------------------------------------- User Book Request & Book Reject Reason ---------------------------------------------------#

@app.route('/user/book-requests')
def user_book_requests():
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get_or_404(session['user_id'])
    user_requests = BookRequest.query.filter_by(user_id=user.id).all()

    return render_template('user_book_requests.html', user=user, user_requests=user_requests)

@app.route('/user/request-book/<int:book_id>')
def user_request_book(book_id):
    if 'user_id' not in session:
        return redirect('/login')

    user = User.query.get_or_404(session['user_id'])
    book = Book.query.get_or_404(book_id)

    # Check if user has reached the maximum limit of 5 requests
    if BookRequest.query.filter(and_(BookRequest.user_id == user.id, BookRequest.status.in_(['Pending Approval', 'Approved']))).count() >= 5:
        flash('You have already requested the maximum number of books. Please return some books to request more.', 'danger')
        return redirect(url_for('cart'))

    existing_request = BookRequest.query.filter_by(user_id=user.id, book_id=book.id).first()

    if (not existing_request) or (existing_request.status != "Approved"):
        new_request = BookRequest(user=user, book=book)
        db.session.add(new_request)
        db.session.commit()
        flash('Your book request has been sent.', 'success')

        # Remove the book from the user's cart after creating the request
        cart_item = Cart.query.filter_by(user=user, book=book).first()
        if cart_item:
            db.session.delete(cart_item)
            db.session.commit()
        return redirect(url_for('user_book_requests'))
    else:
        flash('This book has already been requested. Check your "Book Requests" tab to know the Status.', 'danger')
    
    return redirect(url_for('user_section_details', section_id=book.section.id))

@app.route('/user/unsend-request/<int:request_id>')
def user_unsend_request(request_id):
    user_request = BookRequest.query.get_or_404(request_id)

    if user_request.status == 'Pending Approval':
        db.session.delete(user_request)
        db.session.commit()
        flash('Your book request has been canceled.', 'success')

    return redirect(url_for('user_book_requests'))

@app.route('/user/return-book/<int:request_id>')
def user_return_book(request_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_request = BookRequest.query.get_or_404(request_id)

    user_request.status = 'User Returned'
    user_request.book.return_date = datetime.utcnow()
    db.session.commit()
    flash('Book has been returned successfully.', 'success')

    return redirect(url_for('user_book_requests'))

@app.route('/user/view-rejection-reason/<int:request_id>')
def user_view_rejection_reason(request_id):
    book_request = BookRequest.query.get_or_404(request_id)
    return render_template('librarian_view_rejection_reason.html', reason=book_request, GoBack = 1)

@app.route('/user/view-book/<int:book_id>')
def view_book(book_id):

    book = Book.query.get_or_404(book_id)
    filename = os.path.basename(book.content)
    file_url = url_for('serve_uploaded_file', filename=filename)
    return render_template('user_view_book.html', book=book, file_url=file_url)
   
#----------------------------------------------------- Feedback ---------------------------------------------------#

@app.route('/user/give-feedback/<int:request_id>', methods=['GET', 'POST'])
def user_give_feedback(request_id):
    if 'user_id' not in session:
        return redirect('/login')
    
    user_request = BookRequest.query.get_or_404(request_id)
    user_feedback = Feedback.query.filter_by(user_name=user_request.user.username, book_name=user_request.book.name).order_by(desc(Feedback.date_given)).first()
    feedbacks = Feedback.query.filter_by(book_name=user_request.book.name).all()

    if request.method == 'POST':
        rating = int(request.form['rating'])
        comment = request.form['comment']
        new_feedback = Feedback(user_name=user_request.user.username, book_name=user_request.book.name, rating=rating, comment=comment)
        db.session.add(new_feedback)
        db.session.commit()
        flash('Thank you for your feedback.', 'success')
        
        user_request = BookRequest.query.get_or_404(request_id)
        user_feedback = Feedback.query.filter_by(user_name=user_request.user.username, book_name=user_request.book.name).order_by(desc(Feedback.date_given)).first()
        feedbacks = Feedback.query.filter_by(book_name=user_request.book.name).all()

        return render_template('give_feedback.html', user_request=user_request, user_feedback=user_feedback, feedbacks=feedbacks, overall_ratings_count=calculate_overall_ratings_count(feedbacks), average_rating=calculate_average_rating(feedbacks), GoBack=1)

    return render_template('give_feedback.html', user_request=user_request, user_feedback=user_feedback, feedbacks=feedbacks, overall_ratings_count=calculate_overall_ratings_count(feedbacks), average_rating=calculate_average_rating(feedbacks), GoBack=1)

def calculate_average_rating(feedbacks):
    if not feedbacks:
        return 0.0

    total_ratings = sum(feedback.rating for feedback in feedbacks)
    return total_ratings / len(feedbacks)

def calculate_overall_ratings_count(feedbacks):
    ratings_count = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for feedback in feedbacks:
        ratings_count[feedback.rating] += 1
    return ratings_count

@app.route('/user/view-feedback/<int:book_id>')
def user_view_feedback(book_id):
    book = Book.query.get(book_id)
    user_request = BookRequest.query.filter_by(user_id=session['user_id'], book_id=book_id).first()
    user_feedback = Feedback.query.filter_by(user_name=session['username'], book_name=book.name).order_by(desc(Feedback.date_given)).first()
    feedbacks = Feedback.query.filter_by(book_name=book.name).all()

    return render_template('give_feedback.html', book = book, overall_ratings_count=calculate_overall_ratings_count(feedbacks), user_request=user_request, user_feedback=user_feedback, feedbacks=feedbacks, average_rating=calculate_average_rating(feedbacks), GoBack=0)

#------------------------------------------------------ Search ---------------------------------------------------#

def search_sections(search_query, search_by, search_type):

    if search_type == 'sections':
        if search_by == 'name':
            section_results = search_items(search_query, Section, 'name')
            return section_results
        elif search_by == 'description':
            section_results = search_items(search_query, Section, 'description')
            return section_results
        else:
            raise ValueError("Invalid search_by parameter")
        
    elif search_type == 'books':
        if search_by == 'book_name':
            section_results = search_items(search_query, Book, 'name')
            return section_results
        elif search_by == 'author':
            section_results = search_items(search_query, Book, 'author')
            return section_results
        elif search_by == 'section_name':
            section_results = search_items(search_query, Section, 'name')
            book_results = []
            for section in section_results:
                books = section.books.all()
                book_results.extend(books)
            return book_results
        else:
            raise ValueError("Invalid search_by parameter")
    else:
        raise ValueError("Invalid search_type parameter")

def search_items(search_query, Model, str_param):
    terms = search_query.split()
    items = Model.query
    items_and = items.filter(and_(*[getattr(Model, str_param).ilike(f'%{term}%') for term in terms]))
    items_or = items.filter(or_(*[getattr(Model, str_param).ilike(f'%{term}%') for term in terms]))
    items_combine = items_and.union(items_or)
    item_results = []
    for term in terms:
        items_startswith = items_combine.filter(getattr(Model, str_param).ilike(f'{term}%')).all()
        items_anywhere = items_combine.filter(getattr(Model, str_param).ilike(f'%{term}%')).all()
        item_results.extend(items_startswith)
        item_results.extend(items_anywhere)
    item_results = list(set(item_results))

    def custom_sort(item):
        relevance = sum(term.lower() in getattr(item, str_param).lower() for term in terms)  # Number of terms in the item attribute
        term_positions = [getattr(item, str_param).lower().find(term.lower()) for term in terms]  # Positions of terms in the item attribute
        return (-relevance, min(term_positions))  # Sort by relevance and then by the minimum term position
    
    # Sort items using the custom sorting function
    item_results.sort(key=custom_sort)

    return item_results

# Ensure uploads directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

if __name__ == '__main__':
   with app.app_context():
        db.create_all()
   app.run(debug=True, port=5003, host='0.0.0.0')
else:
    # When run via gunicorn (production), create tables on startup
    with app.app_context():
        db.create_all()