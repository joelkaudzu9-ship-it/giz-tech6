from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, current_app
from app.dashboard import bp
from app.models import Product, Business, Message, Activity, Owner
from app.extensions import db, cache
from app.forms import ProductForm, BusinessSettingsForm
from app.utils.file_handler import FileHandler
from app.utils.decorators import owner_required, ajax_required
from app.utils.analytics import Analytics
from app.utils.email_service import EmailService
from datetime import datetime
import json
import os


# Helper function to get unread messages count
def get_unread_count():
    """Get count of unread messages"""
    return Message.query.filter_by(is_read=False).count()


@bp.route('/')
@owner_required
def overview():
    """Dashboard overview with analytics"""
    # Get business info
    business = Business.query.first()

    # Get unread messages count
    unread_messages = get_unread_count()

    # Get analytics data
    total_revenue = Analytics.get_total_revenue()
    total_views = Analytics.get_total_views()
    sold_count = Analytics.get_sold_count()
    message_count = Analytics.get_message_count()

    # Get recent products
    recent_products = Product.query.order_by(
        Product.date_posted.desc()
    ).limit(5).all()

    # Get recent messages
    recent_messages = Message.query.order_by(
        Message.created_at.desc()
    ).limit(5).all()

    # Get popular products
    popular_products = Analytics.get_popular_products(5)

    # Get recent activity
    recent_activity = Activity.query.order_by(
        Activity.created_at.desc()
    ).limit(10).all()

    # Get sales trend data
    sales_trend = Analytics.get_sales_trend(7)

    return render_template('pages/dashboard/overview.html',
                           business=business,
                           unread_messages=unread_messages,
                           total_revenue=total_revenue,
                           total_views=total_views,
                           sold_count=sold_count,
                           message_count=message_count,
                           recent_products=recent_products,
                           recent_messages=recent_messages,
                           popular_products=popular_products,
                           recent_activity=recent_activity,
                           sales_trend=sales_trend)


@bp.route('/products')
@owner_required
def products():
    """Product management page"""
    business = Business.query.first()
    unread_messages = get_unread_count()
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')

    query = Product.query

    if status == 'sold':
        query = query.filter_by(is_sold=True)
    elif status == 'available':
        query = query.filter_by(is_sold=False)
    elif status == 'featured':
        query = query.filter_by(is_featured=True)
    elif status == 'hidden':
        query = query.filter_by(is_hidden=True)

    pagination = query.order_by(
        Product.date_posted.desc()
    ).paginate(page=page, per_page=10, error_out=False)

    products = pagination.items

    return render_template('pages/dashboard/products.html',
                           business=business,
                           unread_messages=unread_messages,
                           products=products,
                           pagination=pagination,
                           status=status)


@bp.route('/products/add', methods=['GET', 'POST'])
@owner_required
def add_product():
    """Add new product"""
    business = Business.query.first()
    unread_messages = get_unread_count()
    form = ProductForm()

    if form.validate_on_submit():
        # Handle image uploads
        images = []
        if form.images.data:
            files = request.files.getlist('images')
            images = FileHandler.save_images(files, subfolder='products')

        # Create product
        product = Product(
            title=form.title.data,
            price=form.price.data,
            description=form.description.data,
            is_featured=form.is_featured.data,
            seo_title=form.seo_title.data,
            seo_description=form.seo_description.data
        )

        if images:
            product.image_list = images
            product.thumbnail = images[0]  # First image as thumbnail

        db.session.add(product)
        db.session.commit()

        # Send email notification to subscribers about new product
        EmailService.send_product_notification(product, 'new')

        # Track activity
        activity = Activity(
            action='add_product',
            entity_type='product',
            entity_id=product.id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(activity)
        db.session.commit()

        flash('Product added successfully!', 'success')
        return redirect(url_for('dashboard.products'))

    return render_template('pages/dashboard/product-form.html',
                           business=business,
                           unread_messages=unread_messages,
                           form=form,
                           title='Add Product')


@bp.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@owner_required
def edit_product(product_id):
    """Edit existing product"""
    business = Business.query.first()
    unread_messages = get_unread_count()
    product = Product.query.get_or_404(product_id)
    form = ProductForm(obj=product)

    if form.validate_on_submit():
        product.title = form.title.data
        product.price = form.price.data
        product.description = form.description.data
        product.is_featured = form.is_featured.data
        product.seo_title = form.seo_title.data
        product.seo_description = form.seo_description.data

        # Handle new images
        if form.images.data:
            files = request.files.getlist('images')
            new_images = FileHandler.save_images(files, subfolder='products')
            current_images = product.image_list
            current_images.extend(new_images)
            product.image_list = current_images

        product.updated_at = datetime.utcnow()
        db.session.commit()

        flash('Product updated successfully!', 'success')
        return redirect(url_for('dashboard.products'))

    return render_template('pages/dashboard/product-form.html',
                           business=business,
                           unread_messages=unread_messages,
                           form=form,
                           product=product,
                           title='Edit Product')


@bp.route('/products/toggle-sold/<int:product_id>', methods=['POST'])
@owner_required
def toggle_sold(product_id):
    """Toggle product sold status"""
    # Disable CSRF for this endpoint
    from flask_wtf.csrf import csrf_exempt
    csrf_exempt(lambda: None)()

    product = Product.query.get_or_404(product_id)

    product.is_sold = not product.is_sold
    if product.is_sold:
        product.date_sold = datetime.utcnow()
        # Send notification that product is sold
        EmailService.send_product_notification(product, 'sold')

    db.session.commit()

    # Track activity
    activity = Activity(
        action='sold' if product.is_sold else 'available',
        entity_type='product',
        entity_id=product.id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify({
        'success': True,
        'is_sold': product.is_sold,
        'message': f'Product marked as {"sold" if product.is_sold else "available"}'
    })


@bp.route('/products/toggle-featured/<int:product_id>', methods=['POST'])
@owner_required
def toggle_featured(product_id):
    """Toggle product featured status"""
    from flask_wtf.csrf import csrf_exempt
    csrf_exempt(lambda: None)()

    product = Product.query.get_or_404(product_id)
    product.is_featured = not product.is_featured
    db.session.commit()

    return jsonify({
        'success': True,
        'is_featured': product.is_featured
    })


@bp.route('/products/toggle-hidden/<int:product_id>', methods=['POST'])
@owner_required
def toggle_hidden(product_id):
    """Toggle product hidden status"""
    from flask_wtf.csrf import csrf_exempt
    csrf_exempt(lambda: None)()

    product = Product.query.get_or_404(product_id)
    product.is_hidden = not product.is_hidden
    db.session.commit()

    return jsonify({
        'success': True,
        'is_hidden': product.is_hidden
    })


@bp.route('/products/delete/<int:product_id>', methods=['DELETE'])
@owner_required
def delete_product(product_id):
    """Delete product"""
    from flask_wtf.csrf import csrf_exempt
    csrf_exempt(lambda: None)()

    product = Product.query.get_or_404(product_id)

    # Delete associated images
    for image_path in product.image_list:
        FileHandler.delete_image(image_path)

    # Delete product
    db.session.delete(product)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Product deleted successfully'
    })


@bp.route('/messages')
@owner_required
def messages():
    """Message management page"""
    business = Business.query.first()
    unread_messages = get_unread_count()
    page = request.args.get('page', 1, type=int)
    filter_type = request.args.get('filter', 'all')

    query = Message.query

    if filter_type == 'unread':
        query = query.filter_by(is_read=False)
    elif filter_type == 'read':
        query = query.filter_by(is_read=True)

    pagination = query.order_by(
        Message.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)

    messages = pagination.items

    return render_template('pages/dashboard/messages.html',
                           business=business,
                           unread_messages=unread_messages,
                           messages=messages,
                           pagination=pagination,
                           filter_type=filter_type)


@bp.route('/messages/mark-read/<int:message_id>', methods=['POST'])
@owner_required
@ajax_required
def mark_message_read(message_id):
    """Mark message as read"""
    message = Message.query.get_or_404(message_id)
    message.is_read = True
    db.session.commit()

    return jsonify({'success': True})


@bp.route('/messages/delete/<int:message_id>', methods=['DELETE'])
@owner_required
@ajax_required
def delete_message(message_id):
    """Delete message"""
    message = Message.query.get_or_404(message_id)
    db.session.delete(message)
    db.session.commit()

    return jsonify({'success': True})


@bp.route('/analytics')
@owner_required
def analytics():
    """Detailed analytics page"""
    business = Business.query.first()
    unread_messages = get_unread_count()

    # Get date range
    days = request.args.get('days', 30, type=int)

    # Get analytics data with safe defaults
    total_products = Product.query.count()
    total_messages = Message.query.count()
    total_views = db.session.query(db.func.sum(Product.views)).scalar() or 0
    total_revenue = db.session.query(db.func.sum(Product.price)).filter(Product.is_sold == True).scalar() or 0

    # Calculate conversion rate
    conversion_rate = (total_messages / total_views * 100) if total_views > 0 else 0

    # Get popular products
    popular_products = Product.query.order_by(Product.views.desc()).limit(10).all()
    for product in popular_products:
        product.messages_count = Message.query.filter_by(product_id=product.id).count()

    # Create safe sales trend data
    from datetime import datetime, timedelta
    sales_trend = {
        'labels': [],
        'views_data': []
    }

    for i in range(days):
        date = (datetime.utcnow() - timedelta(days=days - i - 1)).strftime('%Y-%m-%d')
        sales_trend['labels'].append(date)
        # You can add real data here if you have daily tracking
        sales_trend['views_data'].append(0)

    # Get messages over time
    from sqlalchemy import func
    messages_over_time = db.session.query(
        func.date(Message.created_at).label('date'),
        func.count(Message.id).label('count')
    ).filter(Message.created_at >= (datetime.utcnow() - timedelta(days=days))).group_by(
        func.date(Message.created_at)).order_by('date').all()

    return render_template('pages/dashboard/analytics.html',
                           business=business,
                           unread_messages=unread_messages,
                           total_products=total_products,
                           total_messages=total_messages,
                           total_views=total_views,
                           total_revenue=total_revenue,
                           conversion_rate=conversion_rate,
                           popular_products=popular_products,
                           sales_trend=sales_trend,
                           messages_over_time=messages_over_time,
                           days=days)


@bp.route('/settings', methods=['GET', 'POST'])
@owner_required
def settings():
    """Business settings page"""
    business = Business.query.first()
    unread_messages = get_unread_count()

    if not business:
        business = Business()
        db.session.add(business)
        db.session.commit()

    form = BusinessSettingsForm(obj=business)

    if form.validate_on_submit():
        business.name = form.name.data
        business.whatsapp = form.whatsapp.data
        business.email = form.email.data
        business.meta_title = form.meta_title.data
        business.meta_description = form.meta_description.data
        business.google_analytics_id = form.google_analytics_id.data
        business.facebook_pixel_id = form.facebook_pixel_id.data

        # Save notification preferences
        business.email_notifications = form.email_notifications.data
        business.whatsapp_notifications = form.whatsapp_notifications.data
        business.daily_digest = form.daily_digest.data

        # Handle logo upload
        if form.logo.data:
            logo_file = form.logo.data
            saved = FileHandler.save_images([logo_file], subfolder='business')
            if saved:
                business.logo = saved[0]

        db.session.commit()

        # Flash message - this will show on the settings page after redirect
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('dashboard.settings'))

    return render_template('pages/dashboard/settings.html',
                           business=business,
                           unread_messages=unread_messages,
                           form=form)


# Export data endpoint
@bp.route('/export-data')
@owner_required
def export_data():
    """Export business data as CSV"""
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