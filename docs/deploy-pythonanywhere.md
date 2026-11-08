# Deploying the backend to PythonAnywhere

PythonAnywhere web apps run on WSGI (uWSGI), but the backend is FastAPI (ASGI).
`backend/wsgi.py` bridges the two with `a2wsgi`. Replace `<username>` below with
your PythonAnywhere username.

> **SSH** is available on paid accounts only (`ssh <username>@ssh.pythonanywhere.com`,
> or `ssh.eu.pythonanywhere.com` on the EU server). On a free account, run
> everything below in a browser **Bash console** (Consoles → Bash).

## 1. Clone and install

```bash
git clone https://github.com/FairHireOrg/fairhire.git
cd ~/fairhire/backend
python3.13 -m venv ~/.virtualenvs/fairhire
source ~/.virtualenvs/fairhire/bin/activate
pip install fastapi uvicorn python-multipart pydantic "openai>=1.0" nltk python-docx python-dotenv a2wsgi
which pdftotext   # required for PDF uploads; preinstalled on PythonAnywhere
```

Do **not** `pip install -r requirements.txt`: it pulls in torch/transformers for
the research pipeline, which the API doesn't use and which won't fit in the free
disk quota.

## 2. Download NLTK stopwords

```bash
chmod go-w ~
mkdir -p ~/nltk_data && chmod 700 ~/nltk_data
NLTK_ALLOW_PROXIED_URLOPEN=1 python -m nltk.downloader -d ~/nltk_data stopwords
python -c "from nltk.corpus import stopwords; print(len(stopwords.words('english')))"
```

The last command should print about 198. Why the extra steps:

- **`Security Violation ... refusing a proxied fetch`**: free accounts send all
  outbound traffic through PythonAnywhere's proxy, which newer NLTK refuses unless
  you opt in. `NLTK_ALLOW_PROXIED_URLOPEN=1` opts in for this one command.
- **`will not authorize the non-private download directory`**: NLTK only writes
  into folders (and parent folders) that aren't group- or world-writable, hence
  the `chmod` lines.
- The `AttributeError: 'NoneType' object has no attribute 'id'` that follows is
  just a crash after the failed download. Fix the two causes above and it goes away.

If this step still fails, the app keeps working: `fairhire/fitness/lexicon.py`
falls back to a built-in stopword list (scores may differ slightly from local runs).

## 3. Optional: DeepSeek key

`.env` is gitignored, so create it on the server:

```bash
cd ~/fairhire/backend && cp .env.example .env && nano .env
```

On free accounts, outbound requests only work for sites on PythonAnywhere's
allowlist. If `api.deepseek.com` isn't on it, "suggest requirements" fails, but
scoring still works because it never calls the LLM.

## 4. Create the web app

1. **Web** tab → **Add a new web app** → **Manual configuration** (not the
   FastAPI/Flask presets) → **Python 3.13**. This must match the virtualenv's version.
2. **Virtualenv**: `/home/<username>/.virtualenvs/fairhire`
3. Open the **WSGI configuration file** link
   (`/var/www/<username>_pythonanywhere_com_wsgi.py`), delete everything, and paste:

   ```python
   import sys
   sys.path.insert(0, "/home/<username>/fairhire/backend")

   from wsgi import application
   ```

4. Click **Reload**.

> Paste this into the `/var/www/...` file, **not** into `backend/wsgi.py`.
> Putting it in `backend/wsgi.py` makes that file import itself:
> `ImportError: cannot import name 'application' from partially initialized module 'wsgi'`.
> To recover, run `git checkout -- backend/wsgi.py`.

## 5. Verify

- `https://<username>.pythonanywhere.com/health` returns `{"status":"ok", ...}`
- `https://<username>.pythonanywhere.com/docs` opens interactive API docs; upload a
  PDF there to test the full parsing flow.

The **server log** should contain `WSGI app 0 (mountpoint='') ready`. For
request failures, check the **error log** (both are linked on the Web tab).

## 6. Connect the frontend

- Set `NEXT_PUBLIC_API_URL=https://<username>.pythonanywhere.com` in the frontend.
- Add the frontend's URL to `allow_origins` in `backend/api.py`. Only `localhost`
  is allowed now, so the browser will block requests from anywhere else.

## Updating

```bash
cd ~/fairhire && git pull
source ~/.virtualenvs/fairhire/bin/activate && pip install <any new deps>
```

Then click **Reload** on the Web tab.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `/health` never loads, but the server log shows the app as ready | `a2wsgi` started its event-loop thread in the uWSGI master, and that thread is gone in the forked worker | Use the current `backend/wsgi.py`, which creates the middleware lazily in each worker. Don't build `ASGIMiddleware` at import time |
| `ImportError ... partially initialized module 'wsgi'` | The PythonAnywhere snippet was pasted into `backend/wsgi.py` | `git checkout -- backend/wsgi.py`; put the snippet in `/var/www/..._wsgi.py` |
| NLTK `Security Violation` / `non-private download directory` | Proxied egress and a group-writable home folder | Step 2 |
| `ModuleNotFoundError` in the error log | Web app uses a different Python version or virtualenv | Web tab: Python 3.13 and the `fairhire` virtualenv |
| CORS errors in the browser | Frontend origin isn't in `allow_origins` | Step 6 |
| Disk quota exceeded during install | Installed `requirements.txt` (torch) | Use the pip line in step 1 |
