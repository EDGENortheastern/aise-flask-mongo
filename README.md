# Flask and Mongo Starter

A [Flask](https://flask.palletsprojects.com/en/stable) + [MongoDB](mongodb.com/docs/languages/python) starter project.

## How to create or run this starter project

### 1. Create a virtual environment

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt)**

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

Your shell prompt should now show `(.venv)`.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

or

```bash
pip install flask pymongo python-dotenv certifi
```

### 3. Freeze dependencies

After installing or upgrading packages, save the exact versions back to `requirements.txt`:

```bash
pip freeze > requirements.txt
```

### 4. Run the app

```bash
python app.py
```

The app starts on [http://localhost:8000](http://localhost:8000).

It needs a MongoDB database reachable at the `MONGO_URI` (defaults to
`mongodb://localhost:27017`). Without one, creating a user shows this error
instead of crashing:

![Database unavailable error](static/no_db_error.png)

### Deactivate

When you're done, leave the virtual environment:

```bash
deactivate
```
