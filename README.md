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

### Deactivate

When you're done, leave the virtual environment:

```bash
deactivate
```
