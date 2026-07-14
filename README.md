# Flask and Mongo Starter

A [Flask](https://flask.palletsprojects.com/en/stable) + [MongoDB](https://www.mongodb.com/docs/languages/python/) starter with session-based authentication and enforced password strength.

**Live demo:** [edgenortheastern.github.io/aise-flask-mongo](https://edgenortheastern.github.io/aise-flask-mongo/) — a tiny launch page that wakes the Render-hosted app (free tier — it sleeps when idle) and takes you there once it answers. In a hurry? Direct link: [aise-flask-mongo.onrender.com](https://aise-flask-mongo.onrender.com), but the first load after idling can take ~30–60 seconds.

## User Docs

This app is deliberately small. Everything a user can do:

1. **Create an account** at `/users/new` with an email and a password. The password must meet **all five** strength rules — at least 8 characters, a lowercase letter, an uppercase letter, a number, and a symbol. A live meter shows which rules are still unmet as you type, and the server re-checks them on submit:

   ![Create user form with the live password strength meter](static/password_strength.png)

2. **Log in** at `/login` with that email and password.
3. **See yourself logged in** at `/users` — the page shows *your own* email and nothing else. There is no way to browse or list other users: each account can only ever see itself.
4. **Log out** with the button in the top-right corner.

That is the whole feature set: register → log in → see your own account → log out.

## Tech Docs

### Libraries

**Main dependencies** — used directly by the app:

| Library | Purpose |
| --- | --- |
| Flask | Web framework: routing, request handling, sessions, flash messages |
| pymongo | MongoDB driver; the `users` collection stores the accounts |
| Werkzeug | `generate_password_hash` / `check_password_hash` for salted password hashing (ships with Flask) |
| python-dotenv | Loads `.env` into environment variables at startup |
| certifi | CA certificate bundle so TLS connections to MongoDB Atlas verify |
| gunicorn | Production WSGI server used on Render (see `Procfile`) |

**Helper dependencies** — pulled in by the main ones:

| Library | Purpose |
| --- | --- |
| Jinja2 | Template engine Flask uses to render `templates/` |
| MarkupSafe | Escapes values in templates (protects against XSS) |
| itsdangerous | Cryptographically signs the session cookie so it cannot be tampered with |
| click | Powers the `flask` command-line interface |
| blinker | Signal/event system Flask uses internally |
| dnspython | Resolves `mongodb+srv://` Atlas connection strings |

**Dev dependency** — `pytest` (in `requirements-dev.txt`) runs the test suite.

### Database connection

[`app.py`](app.py) connects once at startup:

```python
client = MongoClient(
    MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=3000
)
db = client[DB_NAME]
users = db["users"]
```

- `tlsCAFile=certifi.where()` supplies the CA bundle Atlas needs for TLS; it is ignored for plain `mongodb://localhost` connections.
- `serverSelectionTimeoutMS=3000` makes an unreachable database fail after 3 s instead of hanging ~30 s. Every route catches `PyMongoError` and shows a friendly message instead of crashing:

![Database unavailable error](static/no_db_error.png)

### Password strength rules

[`password_strength.py`](password_strength.py) is the single source of truth. Each rule is a `(key, label, test)` tuple:

```python
REQUIREMENTS = [
    ("length", f"at least {MIN_LENGTH} characters", lambda p: len(p) >= MIN_LENGTH),
    ("lowercase", "a lowercase letter", lambda p: bool(re.search(r"[a-z]", p))),
    ("uppercase", "an uppercase letter", lambda p: bool(re.search(r"[A-Z]", p))),
    ("digit", "a number", lambda p: bool(re.search(r"\d", p))),
    ("symbol", "a symbol (e.g. ! ? @ #)", lambda p: bool(re.search(r"[^A-Za-z0-9]", p))),
]
```

`evaluate_password()` counts how many rules pass and only returns `acceptable=True` when **all** of them do. The browser meter in [`static/js/password-strength.js`](static/js/password-strength.js) mirrors these rules for live feedback, but it is only a convenience — it can be bypassed, which is why the server re-checks.

### Registration

[`create_user`](app.py) enforces the rules server-side, rejects duplicate emails, and never stores a plain password:

```python
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
```

`generate_password_hash` produces a salted hash; the original password is never written anywhere.

### Login

[`login`](app.py) verifies the password against the stored hash and deliberately uses **one generic error** for both "no such user" and "wrong password", so the form does not reveal which emails are registered:

```python
if user is None or not check_password_hash(user["password_hash"], password):
    flash("Invalid email or password.", "error")
    return redirect(url_for("login"))

session["user_email"] = email
```

The session cookie is signed with `SECRET_KEY` (via `itsdangerous`), so users cannot forge a login by editing their cookie — **provided a real `SECRET_KEY` is set**. If the env var is missing, the app falls back to a dev-only default (`dev-secret-change-me`) that is public in this repo, so production deployments must set their own.

### Protecting routes

The `login_required` decorator wraps any route that needs a signed-in user:

```python
def login_required(view):
    """Redirect anonymous visitors to the login page."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_email" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped
```

### The account page shows only you

`/users` looks up **only the signed-in user's own document** — it never queries the whole collection, so one account can never enumerate other users' emails:

```python
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
```

### Free-tier wake-up page

Render's free tier puts the app to sleep after ~15 minutes of inactivity, and a sleeping app cannot render its own "please wait" banner — the visitor would just stare at a blank tab for 30–60 seconds. So the waiting room lives *outside* the app: [`docs/index.html`](docs/index.html) is a static page (published with GitHub Pages, which never sleeps) that shows the notice instantly, pings the app, and redirects once it responds:

```js
async function ping(timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    await fetch(APP_URL, {
      mode: "no-cors",
      cache: "no-store",
      signal: controller.signal,
    });
    return true;
  } catch (err) {
    return false;
  } finally {
    clearTimeout(timer);
  }
}
```

`mode: "no-cors"` matters: the app sets no CORS headers, so this page cannot *read* responses from it — and doesn't need to. A resolved fetch means the server answered (awake); a rejected one means it is still waking or unreachable. Render's proxy holds the request open while the container boots, so the ping resolves the moment the app is up.

To publish the page: repository **Settings → Pages → Deploy from a branch → `main` / `docs`**.

### Tests

[`tests/test_app.py`](tests/test_app.py) covers the password rules, registration, login protection, and account-page privacy — **without a real MongoDB**. Each test swaps the module-level `users` collection for an in-memory fake:

```python
@pytest.fixture
def users_col(monkeypatch):
    fake = FakeCollection()
    monkeypatch.setattr(app_module, "users", fake)
    return fake
```

Run them with:

```bash
pip install -r requirements-dev.txt
pytest
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the same suite on every push to `main` and on every pull request.

## Running locally

### 1. Create a virtual environment

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

After installing or upgrading packages, save the exact versions back:

```bash
pip freeze > requirements.txt
```

### 3. Configure the environment

Create a `.env` file (all optional for local development):

```bash
MONGO_URI=mongodb://localhost:27017   # or an Atlas mongodb+srv:// URI
MONGO_DB=py-mongo-starter
SECRET_KEY=...                        # required in production; generate with:
                                      # python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Run the app

```bash
python app.py
```

The app starts on [http://localhost:8000](http://localhost:8000). When you're done, leave the virtual environment with `deactivate`.

## Deployment

[`Procfile`](Procfile) tells Render (or Heroku) how to run the app in production:

```text
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

Set `MONGO_URI`, `MONGO_DB`, and a real `SECRET_KEY` in the service's environment variables. The wake-up page in [`docs/`](docs/) is published separately with GitHub Pages (see [Free-tier wake-up page](#free-tier-wake-up-page)).

## Security notes

- Passwords are stored only as salted hashes (`generate_password_hash`), never in plain text.
- Login failures use one generic message so the form does not reveal registered emails.
- A signed-in user can only ever see their own account; there is no user listing.
- Sessions are only tamper-proof once a real `SECRET_KEY` is set: when the env var is unset, the app silently falls back to the public dev default in `app.py`.
- **Known limitation:** the registration form does reveal whether an email is already taken ("A user with that email already exists"). Fixing this properly needs a different signup flow (e.g. email confirmation), which is out of scope for this starter.

## Tutorial: how this app was built

The git history tells the real story — each step below is one or two actual commits. The order matters: scaffold before code, form before database, security review after features, tests before CI.

### Step 1 — Scaffold the repository (`c58afa4`, `6bef7c2`)

Start with housekeeping, not code: a Python `.gitignore`, a `LICENSE`, a virtual environment, and pinned dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install flask pymongo python-dotenv certifi
pip freeze > requirements.txt
```

Freezing immediately means anyone (including CI, later) can reproduce the exact environment with `pip install -r requirements.txt`.

### Step 2 — Document as you go (`c612356`)

The next commit contained nothing but the setup instructions above, in this README. Writing docs *while* building keeps them accurate; writing them at the end means guessing.

### Step 3 — Registration first, database later (`af35254`)

The first feature: a styled signup form ([`base.html`](templates/base.html) layout + [`new_user.html`](templates/new_user.html)) and a `POST /users` route. This commit also added gunicorn to `requirements.txt` and a `Procfile`, so the project was deployable from its first feature onward. Notably, this commit worked **without any database running** — its message even says so. Two decisions from it still shape the app:

1. **Fail fast, fail friendly.** The Mongo client gets a 3-second timeout and every route catches `PyMongoError`, so with no database reachable the form still renders and shows a clear message instead of hanging or crashing (see [Database connection](#database-connection)).

2. **Hash from day one.** Even though login didn't exist yet, passwords were already stored with `generate_password_hash` — the original code carried the comment *"Passwords are hashed even though there is no login yet"*. Retrofitting hashing later would have meant invalidating every stored password.

### Step 4 — Authentication and password strength (`fe90303`)

This commit added [`password_strength.py`](password_strength.py), the login page, and sessions. The key design choice: the strength rules are **data, not scattered ifs** — a list of `(key, label, test)` tuples (see [Password strength rules](#password-strength-rules)). One definition drives three things:

- the server-side check in `create_user` (the enforcement that matters),
- the requirement checklist rendered into the signup form,
- the live meter in [`password-strength.js`](static/js/password-strength.js), which mirrors the same rules for instant feedback but is never trusted.

Logging in verifies the hash and stores only the email in a signed session cookie:

```python
session["user_email"] = email
```

Routes that need a signed-in user are wrapped with the `login_required` decorator (see [Protecting routes](#protecting-routes)).

### Step 5 — Security review: fix the email leak (`8199cb2`)

The original `/users` page listed **every** user's email to any signed-in account — one account could enumerate the whole membership list. The fix replaced it with an account page that looks up only the signed-in user's own document (see [The account page shows only you](#the-account-page-shows-only-you)).

The same commit added the test suite, so the fix is *proven*, not assumed. The privacy test creates two users, signs in as one, and asserts the other never appears:

```python
assert "You are signed in as:" in body
assert "lola@example.com" in body
assert "lola1@example.com" not in body
```

The tests run against an in-memory `FakeCollection` instead of a real MongoDB (see [Tests](#tests)) — which pays off in the next step.

### Step 6 — Continuous integration (`0e83ee9`)

A GitHub Actions workflow ([`ci.yml`](.github/workflows/ci.yml)) runs the suite in the cloud. As first committed it triggered on every push to any branch; it was later narrowed to pushes on `main` plus pull requests, so a PR doesn't run the same job twice. Because the tests need no database, the workflow is just *checkout → install → pytest* — no services to configure, nothing to keep in sync.

### Step 7 — Deploy, banner, and polish (`2bd2f19`)

The app runs on Render's free tier via the `Procfile` and gunicorn. Free-tier services sleep when idle, so this commit added an in-app "be patient, it's waking up" banner, keyed off the `RENDER` env var the platform sets automatically.

One lesson from this step earned its place in the tutorial: **the live site runs whatever was last pushed and deployed, not your local working tree.** At one point the deployed demo happily accepted the password `123` while the local code demonstrably rejected it — the "bug" was a stale deploy, and the fix was a push and redeploy, not more code.

### Step 8 — The banner paradox: a wake-up page

The banner from step 7 had a flaw hiding in plain sight: it was HTML rendered *by the app*, so during the one stretch where it mattered most — while the app was asleep and a visitor stared at a blank tab — nothing could render it. The fix was to move the waiting room somewhere that never sleeps: [`docs/index.html`](docs/index.html), a static page for GitHub Pages that shows the notice instantly, pings the app, and redirects once it answers (see [Free-tier wake-up page](#free-tier-wake-up-page)). The in-app banner and its context processor were then removed — the static page does the job better.

### If you rebuild this yourself

1. Scaffold and pin dependencies before writing features.
2. Make the app survive missing infrastructure from the start — timeouts and caught errors, not crashes.
3. Hash passwords before you need login, define validation rules once as data, and let the server be the authority.
4. Review your own features for what they *reveal* (user lists, error messages), and encode each fix as a test.
5. Add CI only once the tests run anywhere; deploy early and remember to redeploy.
