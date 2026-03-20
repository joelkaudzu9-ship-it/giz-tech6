def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None
from flask import render_template, request, jsonify, current_app, session, abort
from app.main import bp
from app.models import Product, Business, Message, Activity, Subscriber
from app.extensions import db, cache, limiter
from app.forms import MessageForm
from app.utils.file_handler import FileHandler
from app.utils.validators import sanitize_input, validate_email, is_safe_url  # Fixed this line
from datetime import datetime
import json
import re



@bp.route('/')
@cache.cached(timeout=60)
def index():
    """Homepage with all products"""
    business = Business.query.first()
    products = Product.query.filter_by(is_hidden=False).order_by(
        Product.date_posted.desc()
    ).all()

    # Get featured products
    featured_products = Product.query.filter_by(
        is_featured=True,
        is_hidden=False
    ).limit(6).all()

    return render_template('pages/public/index.html',
                           business=business,
                           products=products,
                           featured_products=featured_products)


@bp.route('/products')
def products():
    """Products listing page with filters"""
    business = Business.query.first()

    # Get query parameters
    page = request.args.get('page', 1, type=int)
    sort = request.args.get('sort', 'newest')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    search = request.args.get('q', '').strip()

    # Base query
    query = Product.query.filter_by(is_hidden=False)

    # Apply filters
    if search:
        query = query.filter(
            Product.title.ilike(f'%{search}%') |
            Product.description.ilike(f'%{search}%')
        )

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    # Apply sorting
    if sort == 'price_low':
        query = query.order_by(Product.price.asc())
    elif sort == 'price_high':
        query = query.order_by(Product.price.desc())
    elif sort == 'views':
        query = query.order_by(Product.views.desc())
    else:  # newest
        query = query.order_by(Product.date_posted.desc())

    # Pagination
    pagination = query.paginate(page=page, per_page=12, error_out=False)
    products = pagination.items

    # Check if AJAX request for infinite scroll
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'html': render_template('components/cards/product-grid-items.html',
                                    products=products),
            'has_next': pagination.has_next,
            'next_page': pagination.next_num if pagination.has_next else None
        })

    return render_template('pages/public/products.html',
                           business=business,
                           products=products,
                           pagination=pagination,
                           sort=sort,
                           search=search)


@bp.route('/product/<identifier>')
def product_detail(identifier):
    """Product detail page - works with both slug and ID"""
    # Try to find by slug first
    product = Product.query.filter_by(slug=identifier, is_hidden=False).first()

    # If not found and identifier is a number, try by ID
    if not product and identifier.isdigit():
        product = Product.query.get(int(identifier))

    if not product:
        abort(404)

    business = Business.query.first()

    # Increment view count
    product.increment_views()

    # Track activity
    activity = Activity(
        action='view',
        entity_type='product',
        entity_id=product.id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    db.session.add(activity)
    db.session.commit()

    # Get related products
    related = Product.query.filter(
        Product.id != product.id,
        Product.is_hidden == False,
        Product.price.between(product.price * 0.7, product.price * 1.3)
    ).order_by(Product.views.desc()).limit(4).all()

    form = MessageForm()

    return render_template('pages/public/product.html',
                           product=product,
                           business=business,
                           related=related,
                           form=form)

from app.utils.notifications import NotificationService


@bp.route('/product/<int:product_id>/message', methods=['POST'])
@limiter.limit("5 per minute")
def send_message(product_id):
    """Send message about product"""
    try:
        product = Product.query.get_or_404(product_id)

        # Get and sanitize form data
        name = sanitize_input(request.form.get('name'), 100)
        email = sanitize_input(request.form.get('email'), 120)
        message_text = sanitize_input(request.form.get('message'), 2000)

        # Validate
        if not all([name, email, message_text]):
            return jsonify({
                'success': False,
                'error': 'All fields are required'
            }), 400

        # Create message
        message = Message(
            name=name,
            email=email,
            message=message_text,
            product_id=product_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )

        db.session.add(message)
        db.session.commit()

        # Track activity
        activity = Activity(
            action='message',
            entity_type='product',
            entity_id=product_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(activity)
        db.session.commit()

        # Send notifications
        NotificationService.send_email_notification(message)
        NotificationService.send_whatsapp_notification(message)

        # Log to console for debugging
        print(f"\n📨 New message for: {product.title}")
        print(f"   From: {name} ({email})")
        print(f"   Message: {message_text[:100]}...")

        return jsonify({
            'success': True,
            'message': 'Message sent successfully! The owner will contact you soon.'
        })

    except Exception as e:
        print(f"Error sending message: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to send message. Please try again.'
        }), 500

def send_message_notification(product, message):
    """Send notifications about new message"""
    # Log to console
    print("\n" + "=" * 60)
    print(f"📨 NEW MESSAGE RECEIVED".center(60))
    print("=" * 60)
    print(f"📦 Product: {product.title}")
    print(f"💰 Price: MWK {product.price:,.2f}")
    print(f"👤 From: {message.name} ({message.email})")
    print(f"💬 Message: {message.message[:200]}{'...' if len(message.message) > 200 else ''}")
    print(f"🔗 Link: /product/{product.id}")
    print(f"📅 Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60 + "\n")

    # TODO: Add email notification
    # TODO: Add SMS notification via WhatsApp Business API
    # TODO: Add push notification for dashboard


def csrf_exempt(f):
    f._csrf_exempt = True
    return f


@bp.route('/message-sent/<int:product_id>')
def message_sent(product_id):
    """Show message confirmation page"""
    product = Product.query.get_or_404(product_id)
    business = Business.query.first()

    return render_template('pages/public/message-sent.html',
                           product=product,
                           business=business)


@bp.route('/search')
def search():
    """Search products (JSON endpoint)"""
    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify({'results': []})

    products = Product.query.filter(
        Product.is_hidden == False,
        Product.title.ilike(f'%{query}%')
    ).limit(10).all()

    results = [{
        'id': p.id,
        'title': p.title,
        'price': p.price,
        'thumbnail': p.thumbnail or (p.image_list[0] if p.image_list else None),
        'url': p.slug or p.id,
        'is_sold': p.is_sold
    } for p in products]

    return jsonify({'results': results})


def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

@bp.route('/subscribe', methods=['POST'])
def subscribe():
    # Skip CSRF check
    if hasattr(request, '_csrf'):
            request._csrf = None
    try:
        data = request.get_json()
        email = data.get('email') if data else request.form.get('email')

        if not email:
            return jsonify({'success': False, 'message': 'Email required'}), 400

        # Import Subscriber model
        from app.models import Subscriber

        # Check if already subscribed
        subscriber = Subscriber.query.filter_by(email=email).first()

        if subscriber:
            if subscriber.is_active:
                return jsonify({'success': False, 'message': 'This email is already subscribed'}), 400
            else:
                subscriber.is_active = True
                subscriber.unsubscribed_at = None
                db.session.commit()
                return jsonify({'success': True, 'message': 'Subscription reactivated successfully!'})

        # Create new subscriber
        subscriber = Subscriber(email=email, is_active=True)
        db.session.add(subscriber)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Successfully subscribed to newsletter!'})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    """Unsubscribe from newsletter"""
    email = request.json.get('email') if request.is_json else request.form.get('email')

    if not email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400

    subscriber = Subscriber.query.filter_by(email=email).first()

    if subscriber and subscriber.is_active:
        subscriber.is_active = False
        subscriber.unsubscribed_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Successfully unsubscribed'})

    return jsonify({'success': False, 'message': 'Email not found or already unsubscribed'}), 404

@bp.route('/test-subscribe', methods=['POST'])
def test_subscribe():
    return jsonify({'success': True, 'message': 'Test route works!'})


def send_welcome_email(email):
    """Send welcome email to new subscriber"""
    # You can implement actual email sending here
    print(f"📧 Welcome email sent to {email}")


@bp.route('/test', methods=['GET'])
def test():
    return "Working"

@bp.route('/sitemap.xml')
def sitemap():
    """Generate sitemap.xml for SEO"""
    from flask import make_response
    from datetime import datetime

    pages = []

    # Static pages
    static_urls = ['', 'products']
    for url in static_urls:
        pages.append({
            'loc': f"{request.url_root}{url}",
            'lastmod': datetime.now().date().isoformat(),
            'changefreq': 'weekly',
            'priority': '1.0' if url == '' else '0.8'
        })

    # Product pages
    products = Product.query.filter_by(is_hidden=False).all()
    for product in products:
        pages.append({
            'loc': f"{request.url_root}product/{product.slug or product.id}",
            'lastmod': product.date_posted.date().isoformat(),
            'changefreq': 'monthly',
            'priority': '0.6'
        })

    sitemap_template = render_template('sitemap.xml', pages=pages)
    response = make_response(sitemap_template)
    response.headers["Content-Type"] = "application/xml"
    return response