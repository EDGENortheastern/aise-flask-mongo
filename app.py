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

# certifi provides the CA bundle needed for TLS connections to MongoDB Atlas.
# It is ignored for plain local connections (mongodb://localhost).
# serverSelectionTimeoutMS keeps requests from hanging ~30s when the database
# is unreachable; instead they fail fast and we show a friendly message.
client = MongoClient(
    MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=3000
)
db = client[DB_NAME]
users = db["users"]


def login_required(view):
    """Redirect anonymous visitors to the login page.

    Wrap any route that should only be reachable once a user has logged in.
    """

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
        return redirect(url_for("list_users"))
    return redirect(url_for("login"))


@app.route("/users/new")
def new_user():
    # The requirements are passed to the template so the on-screen checklist
    # always matches the rules enforced on the server.
    requirements = [
        {"key": key, "label": label} for key, label, _test in REQUIREMENTS
    ]
    return render_template("new_user.html", requirements=requirements)


@app.route("/users", methods=["POST"])
def create_user():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        flash("Email and password are both required.", "error")
        return redirect(url_for("new_user"))

    # Enforce password strength on the server. The browser meter is only a
    # convenience and can be bypassed, so this check is what actually matters.
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
                # Only ever store a salted hash, never the plain password.
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
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    try:
        user = users.find_one({"email": email})
    except PyMongoError:
        flash("Database unavailable. Please try again later.", "error")
        return redirect(url_for("login"))

    # Use one generic message for both "no such user" and "wrong password" so
    # the form does not reveal which emails are registered.
    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    session["user_email"] = email
    flash(f"Welcome back, {email}.", "success")
    return redirect(url_for("list_users"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/users")
@login_required
def list_users():
    try:
        all_users = list(users.find().sort("_id", -1))
    except PyMongoError:
        flash("Database unavailable. Please try again later.", "error")
        all_users = []
    return render_template("users.html", users=all_users)


if __name__ == "__main__":
    app.run(port=8000, debug=True)
