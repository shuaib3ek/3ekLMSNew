from flask_login import UserMixin

class StaffUser(UserMixin):
    """
    A lightweight wrapper that acts as the Flask-Login user for the LMS.
    This user is NEVER saved to the LMS database.
    It purely exists in the user's secure session cookie.
    """
    def __init__(self, user_data):
        self.id = user_data.get('id')
        self.email = user_data.get('email')
        self.first_name = user_data.get('first_name', '')
        self.last_name = user_data.get('last_name', '')
        self.role = user_data.get('role', 'staff')
        
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email
