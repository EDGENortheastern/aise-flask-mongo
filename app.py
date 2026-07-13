import os

import certifi
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from werkzeug.security import generate_password_hash

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


@app.route("/")
def index():
    return redirect(url_for("new_user"))


@app.route("/users/new")
def new_user():
    return render_template("new_user.html")


@app.route("/users", methods=["POST"])
def create_user():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        flash("Email and password are both required.", "error")
        return redirect(url_for("new_user"))

    try:
        if users.find_one({"email": email}):
            flash("A user with that email already exists.", "error")
            return redirect(url_for("new_user"))

        users.insert_one(
            {
                "email": email,
                # Passwords are hashed even though there is no login yet, so we
                # never store them in plain text.
                "password_hash": generate_password_hash(password),
            }
        )
    except PyMongoError:
        flash("Database unavailable. Please try again later.", "error")
        return redirect(url_for("new_user"))

    flash(f"User {email} created.", "success")
    return redirect(url_for("list_users"))


@app.route("/users")
def list_users():
    try:
        all_users = list(users.find().sort("_id", -1))
    except PyMongoError:
        flash("Database unavailable. Please try again later.", "error")
        all_users = []
    return render_template("users.html", users=all_users)


if __name__ == "__main__":
    app.run(port=8000, debug=True)
