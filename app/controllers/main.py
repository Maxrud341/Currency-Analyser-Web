# app/controllers/main.py
from flask import Blueprint, render_template
from app.models.message import Message

main_bp = Blueprint('main', __name__)


@main_bp.route("/")
def index():
    # message = Message.query.first()
    return render_template("index.html")