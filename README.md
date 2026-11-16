# Smart Attendance System

A secure web-based attendance system for universities. Lecturers show a **rotating QR code**; students scan it with their phone, and the server accepts the check-in only if the QR token is authentic and fresh **and** the phone is physically inside the classroom area.

Bachelor thesis project: *Design and Implementation of a Secure Web-Based Smart Attendance System Using QR Code and Geolocation Verification* (University of Debrecen, Computer Science BSc).

## Features

- Three roles: **Admin**, **Lecturer**, **Student** (role-based access control, JWT authentication)
- QR code that changes every 10–300 seconds (HMAC-signed, nothing stored on the server)
- Geofence check (Haversine distance + GPS accuracy limit), one check-in per student per session
- Audit log of every accepted and rejected attempt
- Live roster for the lecturer, CSV export, per-course and system-wide analytics
- Rate limiting, refresh-token blacklist on logout, CSV formula-injection protection

## Project layout

```
backend/    Django + Django REST Framework API (accounts, attendance, config)
frontend/   React single-page app (Vite)
render.yaml Render deployment blueprint
docker-compose.yml  optional local PostgreSQL
```

## Run it locally

Requirements: **Python 3.11+** and **Node.js 20+**. (Docker is optional.)

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows:  .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # Windows:  copy .env.example .env

python manage.py makemigrations accounts attendance   # creates the migration files (commit them!)
python manage.py migrate
python manage.py seed_demo         # demo users, courses and history
python manage.py runserver         # http://localhost:8000
```

### 2. Frontend (second terminal)

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

Open <http://localhost:5173> and sign in with one of the demo accounts (all use the password `Demo1234!`):

| Role     | Username                  |
|----------|---------------------------|
| Admin    | `admin`                   |
| Lecturer | `lecturer1`, `lecturer2`  |
| Student  | `student1` … `student12`  |

`lecturer1` owns the course **INF202** with a ready-made session called *Live demo lecture*.

### 3. Run the tests

```bash
cd backend
python manage.py test
```

The token and geofence tests (`attendance/tests/test_tokens.py`, `test_geo.py`) need no database; `test_api.py` exercises the whole API.

### Optional: PostgreSQL locally

```bash
docker compose up -d db
```

then set `DATABASE_URL=postgres://attendance:attendance@localhost:5432/attendance` in `backend/.env` and run `migrate` and `seed_demo` again.

## Trying a check-in

Browsers only share the location on **HTTPS or localhost**. That decides how you can demo:

| Situation | What to do |
|-----------|-----------|
| **Everything on one laptop** | Set `VITE_DEMO_MODE=true` in `frontend/.env`. The check-in page then lets you type test coordinates instead of using GPS. Log in as lecturer in one browser window and as `student1` in another (private window). Type the same coordinates as the session to succeed (the seeded "Live demo lecture" uses 47.5316, 21.6273; a session you create yourself uses whatever you entered in its form), or coordinates more than the radius away to see a rejection. |
| **Real phone, local app** | Phones need HTTPS. Start a tunnel (e.g. `ngrok http 5173` or Cloudflare Tunnel), put the tunnel's `https://…` address in `FRONTEND_URL` (backend `.env`), restart Django, and open the tunnel address on laptop and phone. Leave `VITE_DEMO_MODE=false`. |
| **Deployed on Render** | HTTPS is automatic, so the real flow works on any phone. |

Seeded coordinates are only a **placeholder in Debrecen**. For a real lecture, the lecturer stands in the room and presses *Use my current location* when creating the session.

## Deploy on Render (free)

1. **Database.** Render's own free PostgreSQL is deleted after 30 days, so create a free database at Neon or Supabase and copy its connection string (it should end with `?sslmode=require`).
2. **Git.** Push the project to GitHub. Make sure `backend/accounts/migrations/` and `backend/attendance/migrations/` are committed (they are created by `makemigrations`).
3. **Blueprint.** In Render choose *New → Blueprint*, select the repository. Render reads `render.yaml` and creates the API and the static site. It asks for the variables marked `sync: false`:
   - `DATABASE_URL`: the connection string from step 1
   - `FRONTEND_URL` and `CORS_ALLOWED_ORIGINS`: the address of the static site (`https://<web-name>.onrender.com`), which you only know after the first deploy; enter a placeholder, then edit the variables and redeploy
   - `VITE_API_URL` (static site): the address of the API (`https://<api-name>.onrender.com`)
4. **First user.** In the API service's *Shell* run `python manage.py createsuperuser` (gives you an ADMIN account). Add lecturers and students in the app under *Users*. Do **not** run `seed_demo` in production.

The free web service sleeps after 15 minutes without requests and needs 30–60 seconds to wake up; open the site a few minutes before a demo.

## Configuration reference

| Variable | Where | Meaning |
|----------|-------|---------|
| `SECRET_KEY` | backend | Django secret and JWT signing key. Required when `DEBUG` is off |
| `DEBUG` | backend | `True` only for development |
| `DATABASE_URL` | backend | PostgreSQL URL; SQLite is used when empty |
| `FRONTEND_URL` | backend | Address students' phones open from the QR code |
| `CORS_ALLOWED_ORIGINS` | backend | Origins allowed to call the API |
| `QR_GRACE_WINDOWS` | backend | How many older QR windows are still accepted (default 1) |
| `MAX_GPS_ACCURACY_M` | backend | Largest accepted GPS error radius (default 100 m) |
| `VITE_API_URL` | frontend | Backend address (empty in development) |
| `VITE_DEMO_MODE` | frontend | `true` enables the test-coordinate panel (**never** in production) |

## API overview

| Method and path | Who | Purpose |
|-----------------|-----|---------|
| `POST /api/auth/login/` | anyone (rate-limited) | JWT access + refresh tokens |
| `POST /api/auth/refresh/`, `/auth/logout/` | signed in | Rotate / blacklist the refresh token |
| `GET /api/auth/me/`, `POST /api/auth/change-password/` | signed in | Profile, password |
| `/api/users/` | admin | User management |
| `/api/courses/` (+ `/students/`, `/analytics/`) | lecturer, admin (students read-only) | Courses, enrolment, analytics |
| `/api/sessions/` (+ `/open/`, `/close/`, `/qr/`, `/attendance/`, `/export/`) | lecturer, admin | Lecture sessions and the live QR |
| `POST /api/attendance/scan/` | student (rate-limited) | Check-in with token and position |
| `GET /api/attendance/my/` | student | Personal dashboard |
| `GET /api/analytics/overview/` | admin | System statistics |

## Security notes and known limits

- A browser can be made to report a **fake GPS position**. The geofence therefore raises the effort needed for proxy attendance, but it is not a proof of presence. It is combined with a short-lived rotating QR code, one personal account per student, a rate limit and an audit log of rejected attempts.
- JWTs are kept in `localStorage` for simplicity. This is exposed to XSS; the app avoids rendering untrusted HTML and the access token lives only 30 minutes.
- Rate-limit counters use Django's in-memory cache, which is per process. With several server processes, switch to a shared cache (e.g. Redis).
- Location data is personal data: keep only what the audit needs and define a retention period (see the thesis chapter on privacy).
