# app/api/routes.py
from flask import jsonify, request, session, current_app
from app.api import bp  # This imports the blueprint
from app.models import Product, Business, Message, Activity
from app.extensions import db, limiter
from app.utils.decorators import ajax_required
from app.utils.analytics import Analytics
from datetime import datetime
import os

@bp.route('/health')
def health():
    # ... rest of your code
    """Health check endpoint for uptime monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '2.0.0'
    })


@bp.route('/stats')
def stats():
    """Public stats endpoint"""
    total_products = Product.query.filter_by(is_hidden=False).count()
    total_views = Analytics.get_total_views()

    return jsonify({
        'total_products': total_products,
        'total_views': total_views,
        'last_updated': datetime.utcnow().isoformat()
    })


@bp.route('/products')
def get_products():
    """Get products list (JSON)"""
    products = Product.query.filter_by(is_hidden=False).order_by(
        Product.date_posted.desc()
    ).all()

    return jsonify([p.to_dict() for p in products])


@bp.route('/product/<int:product_id>')
def get_product(product_id):
    """Get single product details"""
    product = Product.query.get_or_404(product_id)

    if product.is_hidden:
        return jsonify({'error': 'Product not found'}), 404

    return jsonify(product.to_dict())


@bp.route('/track-view/<int:product_id>', methods=['POST'])
def track_view(product_id):
    """Track product view"""
    try:
        product = Product.query.get_or_404(product_id)
        product.views += 1
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 200


@bp.route('/search')
def search_products():
    """Search products API"""
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 10, type=int)

    if len(query) < 2:
        return jsonify([])

    products = Product.query.filter(
        Product.is_hidden == False,
        Product.title.ilike(f'%{query}%')
    ).limit(limit).all()

    return jsonify([{
        'id': p.id,
        'title': p.title,
        'price': p.price,
        'thumbnail': p.thumbnail,
        'slug': p.slug,
        'is_sold': p.is_sold
    } for p in products])


@bp.route('/business-info')
def business_info():
    """Get business information"""
    business = Business.query.first()

    if not business:
        return jsonify({'error': 'Business not found'}), 404

    return jsonify(business.to_dict())


@bp.route('/export-data')
@ajax_required
def export_data():
    """Export business data as CSV"""
    if 'owner_logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    from app.models import Product, Message
    import csv
    from io import StringIO
    from flask import Response

    # Create CSV in memory
    si = StringIO()
    cw = csv.writer(si)

    # Write products header
    cw.writerow(['Products Export'])
    cw.writerow(['ID', 'Title', 'Price', 'Views', 'Sold', 'Featured', 'Created'])
    products = Product.query.all()
    for p in products:
        cw.writerow([p.id, p.title, p.price, p.views, p.is_sold, p.is_featured, p.date_posted])

    cw.writerow([])  # Empty row

    # Write messages header
    cw.writerow(['Messages Export'])
    cw.writerow(['ID', 'Name', 'Email', 'Message', 'Product ID', 'Read', 'Created'])
    messages = Message.query.all()
    for m in messages:
        cw.writerow([m.id, m.name, m.email, m.message, m.product_id, m.is_read, m.created_at])

    output = si.getvalue()

    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=business_export.csv'}
    )


# Dashboard API endpoints (require authentication)
@bp.route('/dashboard/stats')
@ajax_required
def dashboard_stats():
    """Get dashboard statistics"""
    if 'owner_logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    return jsonify({
        'total_revenue': Analytics.get_total_revenue(),
        'total_views': Analytics.get_total_views(),
        'sold_count': Analytics.get_sold_count(),
        'message_count': Analytics.get_message_count(),
        'unread_messages': Analytics.get_message_count(read=False),
        'conversion_rate': Analytics.get_conversion_rate()
    })


@bp.route('/dashboard/recent-activity')
@ajax_required
def recent_activity():
    """Get recent activity for dashboard"""
    if 'owner_logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    limit = request.args.get('limit', 10, type=int)
    activities = Analytics.get_recent_activity(limit)

    return jsonify(activities)


@bp.route('/dashboard/sales-trend')
@ajax_required
def sales_trend():
    """Get sales trend data for charts"""
    if 'owner_logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    days = request.args.get('days', 30, type=int)
    trend = Analytics.get_sales_trend(days)

    return jsonify(trend)


@bp.route('/upload', methods=['POST'])
@limiter.limit("10 per minute")
def upload_file():
    """Generic file upload endpoint"""
    if 'owner_logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    from app.utils.file_handler import FileHandler

    saved = FileHandler.save_images([file], subfolder='temp')

    if saved:
        return jsonify({
            'success': True,
            'url': saved[0]
        })
    else:
        return jsonify({'error': 'Failed to save file'}), 500