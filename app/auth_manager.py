from flask_login import LoginManager


login_manager = LoginManager()

login_manager.login_view = 'auth.login'
login_manager.login_message = "Pro přístup k této stránce se prosím přihlaste."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    return User.query.get(int(user_id))