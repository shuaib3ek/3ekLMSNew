from flask import g, session, abort, request
from app.organizations.models import Organization

def init_tenant():
    """
    Sets the current tenant (Organization) in the Flask global context 'g'.
    Priority: Header > Session > Default 1
    """
    # 1. Check Header (for APIs)
    slug = request.headers.get('X-Organization-Slug')
    org = None
    if slug:
        org = Organization.query.filter_by(slug=slug).first()
            
    if not org:
        # 2. Check Session
        org_id = session.get('organization_id', 1)
        org = Organization.query.get(org_id)
    
    if org:
        g.organization_id = org.id
        g.organization = org
    else:
        # Fallback to default org 1
        org = Organization.query.get(1)
        g.organization_id = 1
        g.organization = org
    
    # if not g.organization:
    #     abort(404, description="Organization context missing")

from flask_login import current_user

def scoped_query(model):
    """
    Returns a query for the given model, automatically filtered by the current organization.
    Usage: scoped_query(Workshop).all()
    """
    if not hasattr(g, 'organization_id'):
        return model.query
        
    # Admins and Super Admins have system-wide visibility across all organizations in the admin console
    if current_user.is_authenticated and current_user.role in ['admin', 'super_admin']:
        return model.query

    return model.query.filter_by(organization_id=g.organization_id)
