from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import bp
from app.models import Owner, Activity
from app.extensions import db, limiter
from app.forms import LoginForm
from app.utils.validators import is_safe_url
from datetime import datetime
import os


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """Owner login page"""
    if current_user.is_authenticated or session.get('owner_logged_in'):
        return redirect(url_for('dashboard.overview'))

    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        remember = form.remember.data

        owner = Owner.query.filter_by(username=username).first()

        if owner and owner.verify_password(password):
            login_user(owner, remember=remember)
            owner.last_login = datetime.utcnow()
            session['owner_logged_in'] = True
            session.permanent = remember
            db.session.commit()

            activity = Activity(
                action='login',
                entity_type='auth',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            db.session.add(activity)
            db.session.commit()

            flash('Welcome back!', 'success')

            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('dashboard.overview'))

        else:
            env_password = os.getenv('OWNER_PASSWORD', 'admin123')
            if username == 'admin' and password == env_password:
                session['owner_logged_in'] = True
                flash('Logged in successfully (legacy mode)', 'success')
                return redirect(url_for('dashboard.overview'))

            flash('Invalid username or password', 'error')

    return render_template('pages/dashboard/login.html', form=form)


@bp.route('/logout')
def logout():
    """Logout owner"""
    if current_user.is_authenticated:
        logout_user()
    session.pop('owner_logged_in', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


@bp.route('/profile')
@login_required
def profile():
    """Owner profile page"""
    return render_template('pages/dashboard/profile.html')


@bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change owner password"""
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not current_password or not new_password or not confirm_password:
        flash('All fields are required', 'error')
        return redirect(url_for('auth.profile'))

    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('auth.profile'))

    if len(new_password) < 8:
        flash('Password must be at least 8 characters long', 'error')
        return redirect(url_for('auth.profile'))

    if current_user.verify_password(current_password):
        current_user.password = new_password
        db.session.commit()
        flash('Password changed successfully', 'success')
    else:
        flash('Current password is incorrect', 'error')

    return redirect(url_for('auth.profile'))


@bp.route('/legacy-login', methods=['POST'])
def legacy_login():
    """Legacy login endpoint"""
    password = request.form.get('password')
    env_password = os.getenv('OWNER_PASSWORD', 'admin123')

    if password == env_password:
        session['owner_logged_in'] = True
        return redirect(url_for('dashboard.overview'))
    else:
        flash('Invalid password', 'error')
        return redirect(url_for('auth.login'))


@bp.route('/test-login')
def test_login():
    from app.models import Owner
    owner = Owner.query.filter_by(username='joelk').first()
    if owner and owner.verify_password('joelkzu.k'):
        return "✅ Login test PASSED! Password works."
    return "❌ Login test FAILED"