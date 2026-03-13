from flask import current_app
from app.crm_client import client as crm_client
from app.crm_client.shadow_sync import (
    update_shadow_trainer, update_shadow_client, 
    update_shadow_contact, update_shadow_staff_user
)

def sync_all_crm_data():
    """
    Background task to perform a 'Full Sweep' of CRM data.
    Ensures the Shadow Database is populated even before the first user request.
    """
    current_app.logger.info("[LMS Sync] Starting Daily CRM Background Sweep...")
    
    # 1. Sync Trainers
    try:
        trainers = crm_client.list_trainers(status='active')
        # list_trainers already calls update_shadow_trainer for each item internally
        current_app.logger.info(f"[LMS Sync] Synced {len(trainers)} trainers.")
    except Exception as e:
        current_app.logger.error(f"[LMS Sync] Trainer sync failed: {e}")

    # 2. Sync Clients
    try:
        clients = crm_client.list_clients()
        # list_clients already calls update_shadow_client internally
        current_app.logger.info(f"[LMS Sync] Synced {len(clients)} clients.")
    except Exception as e:
        current_app.logger.error(f"[LMS Sync] Client sync failed: {e}")

    # 3. Sync Contacts
    try:
        contacts = crm_client.list_contacts()
        # list_contacts already calls update_shadow_contact internally
        current_app.logger.info(f"[LMS Sync] Synced {len(contacts)} contacts.")
    except Exception as e:
        current_app.logger.error(f"[LMS Sync] Contact sync failed: {e}")

    # 4. Sync Staff Users (if possible via a list endpoint)
    # Note: CRM currently might not have a public 'list all staff' for LMS. 
    # If it exists, we'd call it here. For now, Staff sync is opportunistic during login.
    
    current_app.logger.info("[LMS Sync] Daily CRM Background Sweep completed.")
