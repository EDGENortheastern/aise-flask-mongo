import os
from functools import wraps

import certifi
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from werkzeug.security import check_password_hash, generate_password_hash

from password_strength import REQUIREMENTS, evaluate_password

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB", "py-mongo-starter")

client = MongoClient(
    MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=3000
)
db = client[DB_NAME]
users = db["users"]


@app.context_processor
def inject_deploy_flags():
    """Expose on_render so templates can show the free-tier deploy banner."""
    return {"on_render": bool(os.getenv("RENDER"))}


def login_required(view):
    """Redirect anonymous visitors to the login page."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_email" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.route("/")
def index():
    if "user_email" in session:
        return redirect(url_for("account"))
    return redirect(url_for("login"))


@app.route("/users/new")
def new_user():
    """Render the signup form; the requirement checklist mirrors the server rules."""
    requirements = [
        {"key": key, "label": label} for key, label, _test in REQUIREMENTS
    ]
    return render_template("new_user.html", requirements=requirements)


@app.route("/users", methods=["POST"])
def create_user():
    """Create a user, enforcing strength server-side; store only a salted hash."""
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        flash("Email and password are both required.", "error")
        return redirect(url_for("new_user"))

    result = evaluate_password(password)
    if not result["acceptable"]:
        flash(
            "Password is not strong enough. It still needs: "
            + ", ".join(result["unmet"])
            + ".",
            "error",
        )
        return redirect(url_for("new_user"))

    try:
        if users.find_one({"email": email}):
            flash("A user with that email already exists.", "error")
            return redirect(url_for("new_user"))

        users.insert_one(
            {
                "email": email,
                "password_hash": generate_password_hash(password),
            }
        )
    except PyMongoError:
        flash("Database unavailable. Please try again later.", "error")
        return redirect(url_for("new_user"))

    flash(f"Account for {email} created. Please log in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log a user in; one generic error avoids revealing which emails exist."""
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    try:
        user = users.find_one({"email": email})
    except PyMongoError:
        flash("Database unavailable. Please try again later.", "error")
        return redirect(url_for("login"))

    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    session["user_email"] = email
    flash(f"Welcome back, {email}.", "success")
    return redirect(url_for("account"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/users")
@login_required
def account():
    """Show the signed-in user their own account only, never other users."""
    email = session["user_email"]
    try:
        current_user = users.find_one({"email": email})
    except PyMongoError:
        flash("Database unavailable. Please try again later.", "error")
        current_user = None
    return render_template("account.html", current_user=current_user)


if __name__ == "__main__":
    app.run(port=8000, debug=True)
