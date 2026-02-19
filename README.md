# Vault Partners — Full Stack Python App

Built with FastAPI + Jinja2 + SQLAlchemy. 100% Python.

---

## Features
- ✅ Register / Login / Logout
- ✅ Forgot password + email reset link
- ✅ Profile page (name, company, title, phone, bio, LinkedIn, website)
- ✅ Avatar upload + remove
- ✅ Change password
- ✅ Create / Edit / Delete projects
- ✅ File uploads per project (any type)
- ✅ Per-file download and delete
- ✅ Dashboard with project cards

---

## Local Development

```bash
# 1. Clone and enter directory
cd vault-partners

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Edit .env — at minimum change SECRET_KEY

# 5. Run
python main.py
# Visit http://localhost:8000
```

The SQLite database (`vault.db`) is created automatically on first run.

---

## Deploy to Hetzner VPS (Recommended for EU)

```bash
# On your local machine
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '*.db' \
  ./vault-partners/ root@YOUR_SERVER_IP:/var/www/vault-partners/

# On the server
cd /var/www/vault-partners
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up your .env
cp .env.example .env
nano .env   # Fill in SECRET_KEY, DATABASE_URL (postgres), SMTP settings, BASE_URL

# Install and start systemd service
sudo cp vault-partners.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vault-partners
sudo systemctl start vault-partners

# Set up Nginx
sudo cp nginx.conf /etc/nginx/sites-available/vault-partners
sudo ln -s /etc/nginx/sites-available/vault-partners /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d vault-partners.eu -d www.vault-partners.eu
```

---

## Deploy to Railway (Easier)

1. Push this folder to a GitHub repo
2. Go to railway.app → New Project → Deploy from GitHub
3. Add environment variables in Railway's dashboard
4. Railway auto-detects the `Procfile` and deploys

---

## Switch to PostgreSQL (Production)

1. Install: `pip install psycopg2-binary`
2. In `.env`: `DATABASE_URL=postgresql://user:pass@host/dbname`
3. Restart the app — tables are created automatically.

---

## File Structure

```
main.py              ← App entry point
database.py          ← Models + DB session
auth.py              ← Password hashing, session cookies
email_utils.py       ← SMTP email sending
routers/
  auth.py            ← /login /register /logout /forgot /reset
  profile.py         ← /profile and avatar endpoints  
  projects.py        ← /dashboard and /projects/* endpoints
templates/           ← Jinja2 HTML templates
static/              ← CSS, JS, images
uploads/             ← User file storage
  avatars/           ← Profile photos
  projects/          ← Project files
```
