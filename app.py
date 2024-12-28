from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response, session, abort, g
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_minify import Minify
from flask_caching import Cache
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, func
import pandas as pd
import os
import csv
import json
import pytz
import io
from functools import wraps
import markdown
from models import db, User, Pedal, Rating, BlogPost
from slugify import slugify
from urllib.parse import quote
import re

# Initialize Flask app
app = Flask(__name__, 
           template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this to a secure secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'pedals.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Cache configuration
app.config['CACHE_TYPE'] = 'simple'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutes default
cache = Cache(app)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

# Initialize Flask-Minify
Minify(app=app, html=True, js=True, cssless=True)

# Ensure instance folder exists
os.makedirs('instance', exist_ok=True)

# Custom Jinja filters
def slugify(text):
    """Convert text to URL-friendly slug."""
    if not text:
        return ""
    # Remove forward slashes and backslashes completely
    text = text.replace('/', '').replace('\\', '')
    # Remove apostrophes and quotes
    text = text.replace("'", "").replace('"', '')
    # Convert to lowercase and strip whitespace
    text = text.lower().strip()
    # Replace any remaining special characters or multiple spaces with a single hyphen
    text = re.sub(r'[^\w\s-]', '-', text)
    text = re.sub(r'[-\s]+', '-', text)
    # Remove hyphens from start and end
    text = text.strip('-')
    # Replace multiple consecutive hyphens with a single hyphen
    text = re.sub(r'-+', '-', text)
    return text

def get_youtube_embed_url(url):
    """Convert YouTube URL to embed URL."""
    if not url:
        return None
    if 'youtube.com' in url or 'youtu.be' in url:
        if 'youtube.com/watch?v=' in url:
            video_id = url.split('watch?v=')[1].split('&')[0]
            return f'https://www.youtube.com/embed/{video_id}'
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1]
            return f'https://www.youtube.com/embed/{video_id}'
    return url

# Add Jinja2 filters
app.jinja_env.filters['slugify'] = slugify
app.jinja_env.filters['get_youtube_embed_url'] = get_youtube_embed_url

@app.template_filter('markdown_to_html')
def markdown_to_html(text):
    if not text:
        return ""
    return markdown.markdown(text, extensions=['extra'])

@app.template_filter('split_features')
def split_features(features_text):
    if not features_text:
        return []
    # Split by bullet points and clean up each feature
    features = [f.strip() for f in features_text.split('•') if f.strip()]
    return features

# Initialize rate limiter after all other configurations
# limiter = Limiter(
#     app=app,
#     key_func=get_remote_address,
#     default_limits=["1000 per day", "200 per hour"],
#     storage_uri="memory://"
# )

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Import CSV function
def import_csv(file_path):
    try:
        # Clear existing pedals
        Pedal.query.delete()
        db.session.commit()
        
        df = pd.read_csv(file_path)
        # Rename columns to match our model
        df = df.rename(columns={
            'Brand': 'brand',
            'Model': 'pedal_model',
            'Type': 'pedal_type',
            'What Makes It Good': 'what_makes_it_good',
            'My Experience': 'my_experience',
            'Main Features': 'main_features',
            'My Rating': 'my_rating',
            'About Brand': 'about_brand',
            'Best For': 'best_for',
            'Image URL': 'image',
            'Affiliate Link': 'affiliate_link'
        })
        
        for _, row in df.iterrows():
            # Convert rating from string (e.g., '9/10') to float (e.g., 9.0)
            rating_str = str(row['my_rating'])
            if '/' in rating_str:
                num, den = rating_str.split('/')
                rating = float(num)  # Just take the numerator
            else:
                rating = float(rating_str)

            pedal = Pedal(
                brand=row['brand'],
                pedal_model=row['pedal_model'],
                pedal_type=row['pedal_type'],
                what_makes_it_good=row['what_makes_it_good'],
                my_experience=row['my_experience'],
                main_features=row['main_features'],
                my_rating=rating,
                about_brand=row['about_brand'],
                best_for=row['best_for'],
                image=row['image'],
                affiliate_link=row['affiliate_link']
            )
            db.session.add(pedal)
        db.session.commit()
        print(f"Successfully imported {df.shape[0]} pedals from {file_path}")
        return True
    except Exception as e:
        print(f"Error importing CSV: {str(e)}")
        db.session.rollback()
        return False

# Initialize database with sample data
with app.app_context():
    db.create_all()  # Create all tables
    
    # Check if database is empty
    if Pedal.query.count() == 0:
        print("Database is empty. Importing sample data...")
        import_csv('pedals.csv')
    else:
        print(f"Database already contains {Pedal.query.count()} pedals")

@app.route('/')
@cache.cached(timeout=300)  # Cache for 5 minutes
def index():
    try:
        # Get total counts
        total_pedals = Pedal.query.count()
        total_brands = db.session.query(Pedal.brand).distinct().count()
        total_reviews = Rating.query.filter_by(approved=True).count()

        response = make_response(render_template('index.html',
                            total_pedals=total_pedals,
                            total_brands=total_brands,
                            total_reviews=total_reviews))
        response.headers['Cache-Control'] = 'public, max-age=3600, stale-while-revalidate=60'
        return response
    except Exception as e:
        print(f"Error in index route: {str(e)}")
        raise

@app.route('/pedal/<slug>')
@cache.cached(timeout=300, query_string=True)  # Cache for 5 minutes, consider query parameters
def pedal_detail(slug):
    print(f"Debug - Looking for slug: {slug}")  # Debug print
    
    # If the URL doesn't end with -review, redirect to the review version
    if not slug.endswith('-review'):
        return redirect(url_for('pedal_detail', slug=slug + '-review'))

    # Remove the -review suffix for lookup
    lookup_slug = slug.replace('-review', '')
    print(f"Debug - Normalized slug: {lookup_slug}")  # Debug print
    
    # Try to find the pedal by reconstructing the slug
    pedal = None
    pedals = Pedal.query.all()
    print(f"Debug - Total pedals found: {len(pedals)}")  # Debug print
    
    # First try: direct match after normalization
    normalized_lookup = lookup_slug.lower().replace('-', ' ')
    print(f"Debug - Normalized lookup: {normalized_lookup}")  # Debug print
    
    for p in pedals:
        # Create a normalized version of the pedal name
        # Handle special case for "Hard Drive - Distortion"
        normalized_model = p.pedal_model.replace('/', '')
        if ' - ' in normalized_model:
            # Keep the dash with spaces for "Hard Drive - Distortion"
            normalized_model = normalized_model.replace(' - ', '-')
        pedal_name = f"{p.brand} {normalized_model}".lower()
        print(f"Debug - Comparing with: {pedal_name}")  # Debug print
        
        # Try both with and without the dash
        if normalized_lookup == pedal_name.replace('-', ' ') or normalized_lookup == pedal_name:
            pedal = p
            break
    
    # Second try: split by spaces and try different combinations
    if not pedal:
        parts = normalized_lookup.split()
        # Special handling for "jhs pedals" prefix
        if len(parts) >= 2 and parts[0] == 'jhs' and parts[1] == 'pedals':
            brand = 'JHS Pedals'
            model_parts = parts[2:]
            model = ' '.join(model_parts)
            print(f"Debug - Looking for JHS model: {model}")  # Debug print
            
            # Try different variations of the model name
            pedal = Pedal.query.filter(
                Pedal.brand.ilike('JHS Pedals'),
                db.or_(
                    db.func.lower(Pedal.pedal_model) == model.lower(),
                    db.func.lower(Pedal.pedal_model) == model.lower().replace(' ', '-'),
                    db.func.lower(Pedal.pedal_model) == model.lower().replace('-', ' ')
                )
            ).first()
            
            if pedal:
                print(f"Debug - Found pedal: {pedal.brand} {pedal.pedal_model}")  # Debug print

    if pedal is None:
        print("Debug - No pedal found")  # Debug print
        abort(404)

    # Get ratings and reviews
    ratings = Rating.query.filter_by(pedal_id=pedal.id, approved=True).all()
    avg_rating = 0
    if ratings:
        avg_rating = sum([r.rating for r in ratings]) / len(ratings)

    # Get similar pedals
    similar_pedals = Pedal.query.filter(
        db.or_(
            Pedal.brand == pedal.brand,
            # Look for pedals with similar type in the name
            db.or_(
                *[Pedal.pedal_model.ilike(f'%{word}%') 
                  for word in pedal.pedal_model.split()
                  if len(word) > 3]  # Only use words longer than 3 letters
            )
        ),
        Pedal.id != pedal.id  # Exclude the current pedal
    ).limit(4).all()

    response = make_response(render_template('pedal_detail.html', 
                                          pedal=pedal, 
                                          ratings=ratings,
                                          avg_rating=avg_rating,
                                          similar_pedals=similar_pedals))
    response.headers['Cache-Control'] = 'public, max-age=300'  # Cache for 5 minutes
    return response

@app.route('/about')
@cache.cached(timeout=3600)  # Cache for 1 hour
def about():
    response = make_response(render_template('about.html'))
    response.headers['Cache-Control'] = 'public, max-age=3600, stale-while-revalidate=60'
    return response

@app.route('/guides')
def guides():
    return render_template('guides.html')

@app.route('/guides/<guide>')
def guide(guide):
    """Render a specific guide page."""
    # Convert underscores to dashes for template lookup
    template_name = f"guides/{guide}.html"
    return render_template(template_name)

@app.route('/what-are-guitar-pedals')
def what_are_guitar_pedals():
    """Render the what are guitar pedals guide."""
    return render_template('guides/what-are-guitar-pedals.html')

@app.route('/add_rating/<int:pedal_id>', methods=['POST'])
# @limiter.limit("10 per hour")  # Prevent rating spam
def add_rating(pedal_id):
    try:
        rating_value = int(request.form.get('rating'))
        comment = request.form.get('comment')
        author = request.form.get('name')

        pedal = Pedal.query.get_or_404(pedal_id)
        slug = slugify(f"{pedal.brand} {pedal.pedal_model}-review")

        if not all([rating_value, comment, author]):
            flash('Please fill in all fields', 'error')
            return redirect(url_for('pedal_detail', slug=slug))

        new_rating = Rating(
            pedal_id=pedal_id,
            rating=rating_value,
            comment=comment,
            author_name=author
        )
        db.session.add(new_rating)
        db.session.commit()

        flash('Your review has been submitted and is pending approval', 'success')
        return redirect(url_for('pedal_detail', slug=slug))
    except Exception as e:
        pedal = Pedal.query.get_or_404(pedal_id)
        slug = slugify(f"{pedal.brand} {pedal.pedal_model}-review")
        flash('Error submitting review', 'error')
        return redirect(url_for('pedal_detail', slug=slug))

@app.route('/import', methods=['GET', 'POST'])
def import_data():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file uploaded', 400
        file = request.files['file']
        import_csv(file)
        return 'Import successful', 200
    return render_template('import.html')

@app.route('/api/pedals')
# @limiter.limit("30 per minute")  # Rate limit API access
def api_pedals():
    pedals = Pedal.query.all()
    return jsonify([pedal.to_dict() for pedal in pedals])

# Blog routes
@app.route('/blog')
def blog():
    posts = BlogPost.query.filter_by(published=True).order_by(BlogPost.created_at.desc()).all()
    response = make_response(render_template('blog/list.html', posts=posts))
    response.headers['Cache-Control'] = 'public, max-age=3600, stale-while-revalidate=60'
    return response

@app.route('/blog/<slug>')
def blog_post(slug):
    post = BlogPost.query.filter_by(slug=slug, published=True).first_or_404()
    response = make_response(render_template('blog/post.html', post=post))
    response.headers['Cache-Control'] = 'public, max-age=3600, stale-while-revalidate=60'
    return response

# Admin routes
@app.route('/admin/login', methods=['GET', 'POST'])
# @limiter.limit("5 per minute")  # Prevent brute force attacks
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == 'admin' and password == 'Venturedevs1234$':
            user = User.query.filter_by(username='admin').first()
            if not user:
                # Create admin user if it doesn't exist
                user = User(username='admin', password=generate_password_hash('Venturedevs1234$'))
                db.session.add(user)
                db.session.commit()
            
            login_user(user)
            flash('Successfully logged in!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Successfully logged out!', 'success')
    return redirect(url_for('admin_login'))

@app.route('/admin')
@login_required
def admin():
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    total_pedals = Pedal.query.count()
    total_ratings = Rating.query.count()
    pending_ratings = Rating.query.filter_by(approved=False).count()
    total_posts = BlogPost.query.count()
    
    return render_template('admin/dashboard.html',
                         total_pedals=total_pedals,
                         total_ratings=total_ratings,
                         pending_ratings=pending_ratings,
                         total_posts=total_posts)

@app.route('/admin/pedals')
@login_required
def admin_pedals():
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Show 20 pedals per page
    
    # Get filter parameters
    search = request.args.get('search', '').strip()
    pedal_type = request.args.get('type')
    brand = request.args.get('brand')
    
    # Base query
    query = Pedal.query
    
    # Apply filters
    if search:
        search = search.lower()
        combined_name = Pedal.brand.op('||')(' ').op('||')(Pedal.pedal_model)
        query = query.filter(
            or_(
                func.lower(combined_name).contains(search),
                func.lower(Pedal.brand).contains(search),
                func.lower(Pedal.pedal_model).contains(search)
            )
        )
    if pedal_type:
        query = query.filter_by(pedal_type=pedal_type)
    if brand:
        query = query.filter_by(brand=brand)
    
    # Order by brand and model
    query = query.order_by(Pedal.brand, Pedal.pedal_model)
    
    # Paginate
    pedals = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get distinct pedal types and brands for filters
    pedal_types = db.session.query(Pedal.pedal_type).distinct().order_by(Pedal.pedal_type).all()
    brands = db.session.query(Pedal.brand).distinct().order_by(Pedal.brand).all()
    
    return render_template('admin/pedals.html',
                         pedals=pedals,
                         pedal_types=pedal_types,
                         brands=brands,
                         current_type=pedal_type,
                         current_brand=brand,
                         search=search)

@app.route('/admin/pedal/<int:pedal_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_pedal(pedal_id):
    pedal = Pedal.query.get_or_404(pedal_id)
    
    if request.method == 'POST':
        try:
            pedal.brand = request.form.get('brand')
            pedal.pedal_model = request.form.get('pedal_model')  # Changed from 'model' to 'pedal_model'
            pedal.pedal_type = request.form.get('pedal_type')    # Changed from 'type' to 'pedal_type'
            pedal.what_makes_it_good = request.form.get('what_makes_it_good')
            pedal.my_experience = request.form.get('my_experience')
            pedal.main_features = request.form.get('main_features')
            pedal.my_rating = float(request.form.get('my_rating', 0))  # Added float conversion
            pedal.about_brand = request.form.get('about_brand')
            pedal.best_for = request.form.get('best_for')
            pedal.image = request.form.get('image')
            pedal.affiliate_link = request.form.get('affiliate_link')
            pedal.features = request.form.get('features')
            pedal.our_review = request.form.get('our_review')
            pedal.pros = request.form.get('pros')
            pedal.cons = request.form.get('cons')
            pedal.demo = request.form.get('demo')
            pedal.author = request.form.get('author')
            pedal.meta_description = request.form.get('meta_description')  # Added meta_description handling
            
            db.session.commit()
            flash('Pedal updated successfully!', 'success')
            return redirect(url_for('admin_pedals'))
        except Exception as e:
            flash(f'Error updating pedal: {str(e)}', 'error')
    
    return render_template('admin/edit_pedal.html', pedal=pedal)

@app.route('/admin/pedals/<int:pedal_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_pedal(pedal_id):
    try:
        pedal = Pedal.query.get_or_404(pedal_id)
        
        # Delete the pedal and all associated ratings in a single operation
        db.session.delete(pedal)
        db.session.commit()
        
        # Clear cache since we modified the database
        cache.delete_memoized(get_popular_comparisons)
        cache.delete_memoized(pedal_detail, slug=(pedal.brand + ' ' + pedal.pedal_model).lower().replace(' ', '-') + '-review')
        
        flash(f'Successfully deleted {pedal.brand} {pedal.pedal_model}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting pedal: {str(e)}', 'error')
    return redirect(url_for('admin_pedals'))

@app.route('/admin/reviews')
@login_required
def admin_reviews():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    # Get all ratings, ordered by created_at (newest first)
    ratings_pagination = Rating.query.order_by(Rating.created_at.desc()).paginate(page=page, per_page=per_page)
    return render_template('admin/reviews.html', ratings=ratings_pagination)

@app.route('/admin/rating/<int:rating_id>/approve', methods=['POST'])
@login_required
def admin_approve_rating(rating_id):
    rating = Rating.query.get_or_404(rating_id)
    rating.approved = True
    db.session.commit()
    
    # Clear the cache for this pedal's detail page
    pedal = Pedal.query.get(rating.pedal_id)
    if pedal:
        cache.delete_memoized(pedal_detail, slug=(pedal.brand + ' ' + pedal.pedal_model).lower().replace(' ', '-') + '-review')
    
    flash('Rating approved successfully', 'success')
    return redirect(url_for('admin_reviews'))

@app.route('/admin/rating/<int:rating_id>/delete', methods=['POST'])
@login_required
def admin_delete_rating(rating_id):
    rating = Rating.query.get_or_404(rating_id)
    db.session.delete(rating)
    db.session.commit()
    flash('Rating deleted successfully', 'success')
    return redirect(url_for('admin_reviews'))

@app.route('/admin/data')
@login_required
def admin_data():
    return render_template('admin/data.html')

@app.route('/admin/export')
@login_required
def export_pedals():
    try:
        # Query all pedals
        pedals = Pedal.query.all()
        
        # Convert to list of dictionaries
        pedals_data = []
        for pedal in pedals:
            pedal_dict = {
                'Brand': pedal.brand,
                'Model': pedal.pedal_model,
                'Type': pedal.pedal_type,
                'What Makes It Good': pedal.what_makes_it_good,
                'My Experience': pedal.my_experience,
                'Main Features': pedal.main_features,
                'My Rating': pedal.my_rating,
                'About Brand': pedal.about_brand,
                'Best For': pedal.best_for,
                'Image URL': pedal.image,
                'Affiliate Link': pedal.affiliate_link,
                'Features': pedal.features,
                'Our Review': pedal.our_review,
                'Pros': pedal.pros,
                'Cons': pedal.cons,
                'Demo URL': pedal.demo,
                'Author': pedal.author,
                'Meta Description': pedal.meta_description
            }
            pedals_data.append(pedal_dict)
        
        # Convert to DataFrame
        df = pd.DataFrame(pedals_data)
        
        # Create the CSV in memory
        output = io.StringIO()
        df.to_csv(output, index=False)
        
        # Create the response
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=pedals.csv"
        response.headers["Content-type"] = "text/csv"
        
        flash('Data exported successfully', 'success')
        return response
    except Exception as e:
        flash(f'Error exporting data: {str(e)}', 'error')
        return redirect(url_for('admin_data'))

@app.route('/admin/import', methods=['POST'])
# @limiter.limit("10 per hour")  # Limit resource-intensive operations
@login_required
def import_pedals():
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('admin_data'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('admin_data'))
    
    if not file.filename.endswith('.csv'):
        flash('Please upload a CSV file', 'error')
        return redirect(url_for('admin_data'))
    
    try:
        # Read CSV file
        df = pd.read_csv(file)
        
        # Validate required columns
        required_columns = ['Brand', 'Model']
        for col in required_columns:
            if col not in df.columns:
                flash(f'Missing required column: {col}', 'error')
                return redirect(url_for('admin_data'))
        
        # Clear existing pedals if requested
        if request.form.get('clear_existing') == 'yes':
            Pedal.query.delete()
        
        # Import pedals
        for _, row in df.iterrows():
            # Check if pedal already exists (based on brand and model)
            existing_pedal = Pedal.query.filter_by(
                brand=row['Brand'],
                pedal_model=row['Model']
            ).first()
            
            if existing_pedal:
                # Update existing pedal
                existing_pedal.pedal_type = row.get('Type')
                existing_pedal.what_makes_it_good = row.get('What Makes It Good')
                existing_pedal.my_experience = row.get('My Experience')
                existing_pedal.main_features = row.get('Main Features')
                existing_pedal.my_rating = row.get('My Rating')
                existing_pedal.about_brand = row.get('About Brand')
                existing_pedal.best_for = row.get('Best For')
                existing_pedal.image = row.get('Image URL')
                existing_pedal.affiliate_link = row.get('Affiliate Link')
                existing_pedal.features = row.get('Features')
                existing_pedal.our_review = row.get('Our Review')
                existing_pedal.pros = row.get('Pros')
                existing_pedal.cons = row.get('Cons')
                existing_pedal.demo = row.get('Demo URL')
                existing_pedal.author = row.get('Author')
                existing_pedal.meta_description = row.get('Meta Description')
            else:
                # Create new pedal
                pedal = Pedal(
                    brand=row['Brand'],
                    pedal_model=row['Model'],
                    pedal_type=row.get('Type'),
                    what_makes_it_good=row.get('What Makes It Good'),
                    my_experience=row.get('My Experience'),
                    main_features=row.get('Main Features'),
                    my_rating=row.get('My Rating'),
                    about_brand=row.get('About Brand'),
                    best_for=row.get('Best For'),
                    image=row.get('Image URL'),
                    affiliate_link=row.get('Affiliate Link'),
                    features=row.get('Features'),
                    our_review=row.get('Our Review'),
                    pros=row.get('Pros'),
                    cons=row.get('Cons'),
                    demo=row.get('Demo URL'),
                    author=row.get('Author'),
                    meta_description=row.get('Meta Description')
                )
                db.session.add(pedal)
        
        db.session.commit()
        flash('Data imported successfully!', 'success')
        
    except Exception as e:
        flash(f'Error importing data: {str(e)}', 'error')
    
    return redirect(url_for('admin_data'))

@app.route('/admin/clear_pedals', methods=['POST'])
@login_required
def clear_pedals():
    try:
        Pedal.query.delete()
        db.session.commit()
        flash('All pedals have been cleared successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing pedals: {str(e)}', 'error')
    return redirect(url_for('admin_data'))

# Admin blog routes
@app.route('/admin/blog')
@login_required
def admin_blog():
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return render_template('admin/blog/list.html', posts=posts)

@app.route('/admin/blog/new', methods=['GET', 'POST'])
@login_required
def admin_blog_new():
    if request.method == 'POST':
        post = BlogPost(
            title=request.form['title'],
            slug=request.form['slug'],
            content=request.form['content'],
            meta_title=request.form['meta_title'],
            meta_description=request.form['meta_description'],
            featured_image=request.form['featured_image'],
            published='published' in request.form
        )
        db.session.add(post)
        try:
            db.session.commit()
            flash('Blog post created successfully!', 'success')
            return redirect(url_for('admin_blog'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating blog post. Please try again.', 'error')
            return render_template('admin/blog/edit.html', post=None)
    return render_template('admin/blog/edit.html', post=None)

@app.route('/admin/blog/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_blog_edit(id):
    post = BlogPost.query.get_or_404(id)
    if request.method == 'POST':
        post.title = request.form['title']
        post.slug = request.form['slug']
        post.content = request.form['content']
        post.meta_title = request.form['meta_title']
        post.meta_description = request.form['meta_description']
        post.featured_image = request.form['featured_image']
        post.published = 'published' in request.form
        try:
            db.session.commit()
            flash('Blog post updated successfully!', 'success')
            return redirect(url_for('admin_blog'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating blog post. Please try again.', 'error')
    return render_template('admin/blog/edit.html', post=post)

@app.route('/admin/blog/delete/<int:id>', methods=['POST'])
@login_required
def admin_blog_delete(id):
    post = BlogPost.query.get_or_404(id)
    try:
        db.session.delete(post)
        db.session.commit()
        flash('Blog post deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting blog post. Please try again.', 'error')
    return redirect(url_for('admin_blog'))

@app.route('/compare_pedals', methods=['GET', 'POST'])
def compare_pedals():
    if request.method == 'POST':
        pedal1_name = request.form.get('pedal1', '').strip()
        pedal2_name = request.form.get('pedal2', '').strip()
        
        if not pedal1_name or not pedal2_name:
            flash('Please select two pedals to compare.', 'warning')
            return redirect(url_for('compare_pedals'))
        
        # Create slugs from pedal names using the same slugify function
        pedal1_slug = slugify(pedal1_name)
        pedal2_slug = slugify(pedal2_name)
        
        return redirect(url_for('compare_pedals_by_slug', pedal1=pedal1_slug, pedal2=pedal2_slug))
    
    # Get all pedals for search suggestions
    pedals = Pedal.query.with_entities(Pedal.brand, Pedal.pedal_model).all()
    pedal_suggestions = [f"{p.brand} {p.pedal_model}" for p in pedals]
    
    response = make_response(render_template('compare.html', 
                         pedal1=None, 
                         pedal2=None, 
                         pedal_suggestions=pedal_suggestions,
                         similar_pedals=[]))
    response.headers['Cache-Control'] = 'public, max-age=3600, stale-while-revalidate=60'
    return response

@app.route('/compare/<pedal1>-vs-<pedal2>')
@cache.cached(timeout=300)  # Cache for 5 minutes
def compare_pedals_by_slug(pedal1, pedal2):
    # Check if trying to compare the same pedal
    if pedal1 == pedal2:
        flash('You cannot compare a pedal with itself. Please select two different pedals.', 'warning')
        return redirect(url_for('compare_pedals'))

    pedal1_obj = None
    pedal2_obj = None
    pedal1_ratings = []
    pedal2_ratings = []
    pedal1_avg_rating = 0
    pedal2_avg_rating = 0
    pedal1_reviews = []
    pedal2_reviews = []
    
    def find_pedal(slug):
        # Remove -review suffix if present
        lookup_slug = slug.replace('-review', '')
        
        # Try exact match first
        pedals = Pedal.query.all()
        for p in pedals:
            # Create a slug from the brand and model using the same slugify function
            pedal_slug = slugify(f"{p.brand} {p.pedal_model}")
            if lookup_slug == pedal_slug:
                return p
        
        # If no exact match, try fuzzy matching
        for p in pedals:
            if slugify(f"{p.brand} {p.pedal_model}") in lookup_slug or lookup_slug in slugify(f"{p.brand} {p.pedal_model}"):
                return p
        
        return None

    pedal1_obj = find_pedal(pedal1)
    pedal2_obj = find_pedal(pedal2)

    if not pedal1_obj or not pedal2_obj:
        flash('One or both pedals not found. Please try again.', 'error')
        return redirect(url_for('compare_pedals'))

    # Get ratings and reviews for pedal 1
    if pedal1_obj:
        pedal1_ratings = Rating.query.filter_by(pedal_id=pedal1_obj.id).all()
        pedal1_avg_rating = sum([r.rating for r in pedal1_ratings]) / len(pedal1_ratings) if pedal1_ratings else 0
        pedal1_reviews = Rating.query.filter_by(pedal_id=pedal1_obj.id, approved=True).all()

    # Get ratings and reviews for pedal 2
    if pedal2_obj:
        pedal2_ratings = Rating.query.filter_by(pedal_id=pedal2_obj.id).all()
        pedal2_avg_rating = sum([r.rating for r in pedal2_ratings]) / len(pedal2_ratings) if pedal2_ratings else 0
        pedal2_reviews = Rating.query.filter_by(pedal_id=pedal2_obj.id, approved=True).all()

    # Get similar pedals
    similar_pedals = []
    if pedal1_obj and pedal2_obj:
        # Get pedals with the same type as either of the compared pedals
        similar_pedals = Pedal.query.filter(
            Pedal.id.notin_([pedal1_obj.id, pedal2_obj.id]),
            Pedal.pedal_type.in_([pedal1_obj.pedal_type, pedal2_obj.pedal_type])
        ).limit(4).all()

    # Get all pedals for search suggestions
    pedals = Pedal.query.with_entities(Pedal.brand, Pedal.pedal_model).all()
    pedal_suggestions = [f"{p.brand} {p.pedal_model}" for p in pedals]

    response = make_response(render_template('compare.html',
                         pedal1=pedal1_obj,
                         pedal2=pedal2_obj,
                         pedal1_ratings=pedal1_ratings,
                         pedal2_ratings=pedal2_ratings,
                         pedal1_avg_rating=pedal1_avg_rating,
                         pedal2_avg_rating=pedal2_avg_rating,
                         pedal1_reviews=pedal1_reviews,
                         pedal2_reviews=pedal2_reviews,
                         similar_pedals=similar_pedals,
                         pedal_suggestions=pedal_suggestions))
    response.headers['Cache-Control'] = 'public, max-age=3600, stale-while-revalidate=60'
    return response

def get_popular_comparisons():
    """Get list of popular pedal comparisons based on certain criteria"""
    popular_pairs = []
    pedals = Pedal.query.all()
    pedal_dict = {pedal.id: pedal for pedal in pedals}
    
    # Get comparisons that have been viewed the most (if you track views)
    # For now, we'll create strategic pairs:
    # 1. Compare pedals of the same type
    # 2. Compare pedals in similar price ranges
    # 3. Limit to a reasonable number
    
    pedals_by_type = {}
    for pedal in pedals:
        if pedal.pedal_type:
            if pedal.pedal_type not in pedals_by_type:
                pedals_by_type[pedal.pedal_type] = []
            pedals_by_type[pedal.pedal_type].append(pedal)
    
    # Create pairs of pedals of the same type
    MAX_PAIRS_PER_TYPE = 10  # Limit pairs per type
    for pedal_type, type_pedals in pedals_by_type.items():
        pairs_count = 0
        for i in range(len(type_pedals)):
            if pairs_count >= MAX_PAIRS_PER_TYPE:
                break
            for j in range(i + 1, len(type_pedals)):
                if pairs_count >= MAX_PAIRS_PER_TYPE:
                    break
                pedal1 = type_pedals[i]
                pedal2 = type_pedals[j]
                # Always order pedals alphabetically for consistency
                if f"{pedal1.brand} {pedal1.pedal_model}" > f"{pedal2.brand} {pedal2.pedal_model}":
                    pedal1, pedal2 = pedal2, pedal1
                popular_pairs.append((pedal1, pedal2))
                pairs_count += 1
    
    return popular_pairs

def get_sitemap_urls():
    """Generate list of URLs for sitemap"""
    urls = []
    
    # Add static pages
    urls.append({"loc": url_for('index', _external=True), "priority": "1.0"})
    urls.append({"loc": url_for('pedals', _external=True), "priority": "0.9"})
    urls.append({"loc": url_for('about', _external=True), "priority": "0.7"})
    urls.append({"loc": url_for('compare_pedals', _external=True), "priority": "0.8"})
    urls.append({"loc": url_for('privacy', _external=True), "priority": "0.6"})
    
    # Add guides
    guides = [
        'what-are-guitar-pedals',
        'how-to-choose-guitar-pedals',
        'guitar-pedal-chain',
        'pedals-for-beginners',
        'are-pedals-necessary'
    ]
    for guide in guides:
        urls.append({
            "loc": url_for('guide', guide=guide, _external=True),
            "priority": "0.8"
        })
    
    # Add all pedal pages
    pedals = Pedal.query.all()
    for pedal in pedals:
        urls.append({
            "loc": url_for('pedal_detail', 
                          slug=slugify(f"{pedal.brand} {pedal.pedal_model}") + '-review', 
                          _external=True),
            "priority": "0.7"
        })
    
    # Add blog posts
    blog_posts = BlogPost.query.filter_by(published=True).all()
    for post in blog_posts:
        urls.append({
            "loc": url_for('blog_post', slug=post.slug, _external=True),
            "priority": "0.6",
            "lastmod": post.updated_at.strftime('%Y-%m-%d')
        })
    
    return urls

@app.route('/sitemap.xml')
def sitemap():
    """Generate sitemap.xml"""
    urls = get_sitemap_urls()
    
    xml_content = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_content.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    for url in urls:
        xml_content.append('  <url>')
        # Escape any special characters in the URL
        safe_loc = url['loc'].replace('&', '&amp;').replace("'", '&apos;').replace('"', '&quot;')
        xml_content.append(f'    <loc>{safe_loc}</loc>')
        if 'lastmod' in url and url['lastmod']:
            xml_content.append(f'    <lastmod>{url["lastmod"]}</lastmod>')
        xml_content.append(f'    <priority>{url["priority"]}</priority>')
        xml_content.append('  </url>')
    
    xml_content.append('</urlset>')
    
    response = make_response('\n'.join(xml_content))
    response.headers['Content-Type'] = 'application/xml'
    response.headers['Content-Language'] = 'en'
    response.headers['Cache-Control'] = 'max-age=3600'
    return response

@app.route('/robots.txt')
def robots():
    response = make_response("""User-agent: *
Allow: /
Allow: /pedal/*-review
Allow: /blog/*
Allow: /guides/*
Allow: /compare/*
Allow: /about
Allow: /privacy-policy
Disallow: /admin/*
""")
    response.headers["Content-Type"] = "text/plain"
    return response

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('admin_login'))

@app.route('/admin/clear-cache', methods=['POST'])
@login_required
@admin_required
def clear_cache():
    """Clear the application cache."""
    with app.app_context():
        cache.clear()
        flash('Cache cleared successfully', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update-slugs', methods=['POST'])
@login_required
@admin_required
def update_slugs():
    try:
        pedals = Pedal.query.all()
        for pedal in pedals:
            # Update the slug using the new slugify function
            new_slug = slugify(f"{pedal.brand} {pedal.pedal_model}")
            pedal.slug = new_slug
        db.session.commit()
        cache.delete_memoized(get_sitemap_urls)  # Clear sitemap cache
        flash('All pedal slugs have been updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating slugs: {str(e)}', 'error')
    return redirect(url_for('admin_data'))

@app.route('/pedals')
@cache.cached(timeout=300, query_string=True)  # Cache for 5 minutes, consider query parameters
def pedals():
    page = request.args.get('page', 1, type=int)
    per_page = 24

    # Get filter parameters
    search = request.args.get('search', '').strip()
    brand = request.args.get('brand', '')
    pedal_type = request.args.get('type', '')
    min_rating = request.args.get('min_rating', type=float)
    sort = request.args.get('sort', 'newest')  # Default sort by newest

    # Base query
    query = Pedal.query

    # Apply search
    if search:
        search = search.lower()
        combined_name = Pedal.brand.op('||')(' ').op('||')(Pedal.pedal_model)
        query = query.filter(
            or_(
                func.lower(combined_name).contains(search),
                func.lower(Pedal.brand).contains(search),
                func.lower(Pedal.pedal_model).contains(search)
            )
        )

    # Apply filters
    if brand:
        query = query.filter(Pedal.brand == brand)
    if pedal_type:
        query = query.filter(Pedal.pedal_type == pedal_type)
    if min_rating is not None:
        query = query.filter(Pedal.my_rating >= min_rating)

    # Apply sorting
    if sort == 'rating':
        query = query.order_by(Pedal.my_rating.desc())
    else:  # newest
        query = query.order_by(Pedal.id.desc())

    # Get unique brands and types for filters
    brands = db.session.query(Pedal.brand).distinct().order_by(Pedal.brand).all()
    types = db.session.query(Pedal.pedal_type).distinct().order_by(Pedal.pedal_type).all()

    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    pedals = pagination.items

    # Cache the response for better performance
    response = make_response(render_template(
        'pedals.html',
        pedals=pedals,
        pagination=pagination,
        brands=[brand[0] for brand in brands],
        types=[type[0] for type in types],
        current_type=pedal_type,
        current_brand=brand,
        current_min_rating=min_rating,
        current_sort=sort,
        current_search=search
    ))
    response.headers['Cache-Control'] = 'public, max-age=300'  # Cache for 5 minutes
    return response

# Rate limit error handlers
# @app.errorhandler(429)  # Too Many Requests
# def ratelimit_handler(e):
#     return make_response(
#         render_template('error.html',
#                        error_code=429,
#                        error_message="Too many requests. Please try again later."),
#         429
#     )

@app.route('/privacy-policy')
@cache.cached(timeout=3600)  # Cache for 1 hour
def privacy():
    response = make_response(render_template('privacy.html'))
    response.headers['Cache-Control'] = 'public, max-age=3600, stale-while-revalidate=60'
    return response

@app.route('/privacy')
def privacy_redirect():
    return redirect(url_for('privacy'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=2913)
