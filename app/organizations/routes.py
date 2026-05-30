from flask import render_template, redirect, url_for, flash, request, g, session
from flask_login import login_required, current_user
from app.organizations import organizations_bp
from app.organizations.models import Organization
from app.core.extensions import db
from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'super_admin']:
            flash("Administrative privileges required.", "danger")
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@organizations_bp.route('/')
@login_required
@admin_required
def list_organizations():
    orgs = Organization.query.all()
    return render_template('organizations/list.html', organizations=orgs)

@organizations_bp.route('/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_organization():
    if request.method == 'POST':
        name = request.form.get('name')
        slug = request.form.get('slug')
        primary_color = request.form.get('primary_color', '#0ea5e9')
        logo_url = request.form.get('logo_url')
        
        if not name or not slug:
            flash("Name and Slug are required.", "warning")
            return render_template('organizations/form.html', organization=None)
            
        if Organization.query.filter_by(slug=slug).first():
            flash("Slug already exists. Choose another.", "warning")
            return render_template('organizations/form.html', organization=None)
            
        org = Organization(
            name=name, 
            slug=slug, 
            primary_color=primary_color, 
            logo_url=logo_url,
            allow_self_registration='allow_self_registration' in request.form,
            permitted_domains=request.form.get('permitted_domains')
        )
        db.session.add(org)
        db.session.commit()
        
        flash(f"Organization '{name}' created successfully.", "success")
        return redirect(url_for('organizations.list_organizations'))
        
    return render_template('organizations/form.html', organization=None)

@organizations_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_organization(id):
    org = Organization.query.get_or_404(id)
    if request.method == 'POST':
        org.name = request.form.get('name')
        org.primary_color = request.form.get('primary_color', '#0ea5e9')
        org.logo_url = request.form.get('logo_url')
        org.is_active = 'is_active' in request.form
        org.allow_self_registration = 'allow_self_registration' in request.form
        org.permitted_domains = request.form.get('permitted_domains')
        db.session.commit()
        flash(f"Organization '{org.name}' updated.", "success")
        return redirect(url_for('organizations.list_organizations'))
    return render_template('organizations/form.html', organization=org)

@organizations_bp.route('/switch/<int:id>')
@login_required
@admin_required
def switch_tenant(id):
    org = Organization.query.get_or_404(id)
    session['organization_id'] = org.id
    flash(f"Switched to context: {org.name}", "success")
    return redirect(url_for('admin.dashboard'))

@organizations_bp.route('/t/<slug>')
def tenant_entry(slug):
    """
    Public entry point for a specific tenant.
    Sets the session context and redirects to the public workshop catalog.
    """
    org = Organization.query.filter_by(slug=slug, is_active=True).first_or_404()
    session['organization_id'] = org.id
    # Redirect to the login page for this tenant
    return redirect(url_for('auth.login'))
