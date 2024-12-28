from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from slugify import slugify

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

class Pedal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(100), nullable=False)
    pedal_model = db.Column(db.String(100), nullable=False)
    pedal_type = db.Column(db.String(50), nullable=False)
    what_makes_it_good = db.Column(db.Text)
    my_experience = db.Column(db.Text)
    main_features = db.Column(db.Text)
    my_rating = db.Column(db.Float)
    about_brand = db.Column(db.Text)
    best_for = db.Column(db.Text)
    image = db.Column(db.String(500))
    affiliate_link = db.Column(db.String(500))
    features = db.Column(db.Text)
    our_review = db.Column(db.Text)
    pros = db.Column(db.Text)
    cons = db.Column(db.Text)
    demo = db.Column(db.String(500))  # YouTube demo URL
    author = db.Column(db.Text)  # Author information
    meta_description = db.Column(db.String(300))  # Meta description for SEO

    def __repr__(self):
        return f'<Pedal {self.brand} {self.pedal_model}>'

    def to_dict(self):
        return {
            'id': self.id,
            'brand': self.brand,
            'pedal_model': self.pedal_model,
            'pedal_type': self.pedal_type,
            'what_makes_it_good': self.what_makes_it_good,
            'my_experience': self.my_experience,
            'main_features': self.main_features,
            'my_rating': self.my_rating,
            'about_brand': self.about_brand,
            'best_for': self.best_for,
            'image': self.image,
            'affiliate_link': self.affiliate_link,
            'features': self.features,
            'our_review': self.our_review,
            'pros': self.pros,
            'cons': self.cons,
            'demo': self.demo,
            'author': self.author,
            'meta_description': self.meta_description
        }

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedal_id = db.Column(db.Integer, db.ForeignKey('pedal.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    author_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved = db.Column(db.Boolean, default=False)
    
    pedal = db.relationship('Pedal', backref=db.backref('ratings', lazy=True))

    def __repr__(self):
        return f'<Rating {self.id} for Pedal {self.pedal_id}>'

class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    meta_title = db.Column(db.String(200))
    meta_description = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published = db.Column(db.Boolean, default=False)
    featured_image = db.Column(db.String(500))

    def __init__(self, *args, **kwargs):
        if not kwargs.get('slug') and kwargs.get('title'):
            kwargs['slug'] = slugify(kwargs.get('title'))
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return f'<BlogPost {self.title}>'
