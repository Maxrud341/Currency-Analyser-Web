from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User
from app import db
from app import get_logger

logger = get_logger('auth')
auth_bp = Blueprint('auth', __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    # if current_user.is_authenticated :
    #     return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        logger.info(f"[LOGIN] Login attempt for email: {email}")

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            logout_user()
            login_user(user)
            logger.info(f"[LOGIN] SUCCESS: User {email} logged in")
            return redirect(url_for("main.index"))


        logger.warning(f"[LOGIN] FAILED: Invalid credentials for {email}")
        flash("Neplatný e-mail nebo heslo.", "login_danger")
        return redirect(url_for("auth.login"))

    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Handle new user registration and auto-login."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        logger.info(f"[REGISTER] Registration attempt for email: {email}")

        if password != confirm_password:
            logger.warning(f"[REGISTER] FAILED: Passwords mismatch for {email}")

            flash("Hesla se neshodují!", "register_warning")
            return redirect(url_for("auth.register"))

        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            logger.warning(f"[REGISTER] FAILED: User {email} already exists")

            flash("Uživatel s tímто e-mailem již existuje.", "register_info")
            return redirect(url_for("auth.register"))

        try:
            new_user = User(name=name, email=email)
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()

            login_user(new_user)

            logger.info(f"[REGISTER] SUCCESS: User {email} created and automatically logged in")
            flash("Registrace byla úspěšná! Vítejte v systému.", "success")

            return redirect(url_for("main.index"))

        except Exception as e:
            db.session.rollback()
            logger.error(f"[REGISTER] ERROR: Could not create user {email}. Exception: {str(e)}")

            flash("Došlo k chybě při ukládání do databáze.", "register_danger")
            return redirect(url_for("auth.register"))

    return render_template("register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """Clear user session."""
    user_email = current_user.email
    logout_user()
    logger.info(f"[LOGOUT] User {user_email} logged out")
    return redirect(url_for("auth.login"))

@auth_bp.route("/switch-user")
def switch_user():
    return redirect(url_for("auth.login"))