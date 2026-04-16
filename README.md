# CineBook

A full-stack movie theater management and ticket booking application with dynamic demand pricing, smart recommendations, and admin demand forecasting.

**Course:** Database Systems — Project Stage 4  
**Team:** Melissa Le · Fanta Amouzougan · Vanohra Gaspard  
**Repo:** github.com/melissale05/CineBook

---

## What Was Built

| Milestone | Status | Description |
|-----------|--------|-------------|
| 1 — DB Init | **Complete** | schema.sql, seed.sql, init scripts, TMDB fetch |
| 2 — Backend API | **Complete** | FastAPI app, auth, CRUD endpoints, dynamic pricing |
| 3 — Advanced SQL | **Complete** | Stored procedures, window functions, triggers, forecasting |
| 4 — Frontend | **Complete** | 6-page HTML/JS UI fully connected to backend |
| 5 — Testing/Demo | **Complete** | Demo script, validation tests, run instructions |

---

## Quick Start (Run Locally for Demo)

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ running locally
- A `cinebook_user` database user (see below)

### 1 — Clone & install dependencies

```bash
git clone https://github.com/melissale05/CineBook
cd CineBook
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2 — Create PostgreSQL user

In pgAdmin 4 or psql (as superuser):

```sql
CREATE USER cinebook_user WITH PASSWORD 'DataDivas';
ALTER USER cinebook_user CREATEDB;
```

The `.env` file is already configured with these credentials.

### 3 — Initialize the database

```bash
# Creates the cinebook database, applies schema + advanced SQL
python scripts/init_db.py
```

### 4 — Load seed data

```bash
# Inserts test users, theaters, movies, showtimes, bookings, forecasts
# Also hashes all passwords with bcrypt
python scripts/seed_db.py
```

### 5 — Apply advanced SQL (stored procedures, triggers, views)

In pgAdmin → cinebook database → Query Tool, run:

```
database/recommendations_and_forecasting.sql
```

Or from psql:

```bash
psql -U cinebook_user -d cinebook -f database/recommendations_and_forecasting.sql
```

### 6 — (Optional) Fetch live TMDB metadata

```bash
python scripts/fetch_tmdb.py
```

### 7 — Start the backend

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at **http://localhost:8000**  
Interactive docs: **http://localhost:8000/docs**

### 8 — Open the frontend

Open any of the HTML files directly in your browser:

```
CineBook_Frontend/homepage.html    ← Start here
```

Or, since CORS is enabled, you can open `http://localhost:8000/` (served from FastAPI).

---

## Seed Test Accounts

| Email | Password | Role | Favorite Genre |
|---|---|---|---|
| admin@cinebook.com | AdminPass!23 | **admin** | — |
| alice@example.com | password123 | customer | Action |
| bob@example.com | password123 | customer | Horror |
| david@example.com | password123 | customer | Sci-Fi |
| carol@example.com | password123 | customer | Romance |

---

## Project Structure

```
CineBook/
├── app/
│   ├── main.py                  # FastAPI entry point (uvicorn app.main:app)
│   ├── sessions.py              # In-memory session token store
│   ├── dependencies.py          # Auth dependency (get_current_user)
│   ├── core/
│   │   └── config.py            # Reads .env
│   ├── db/
│   │   └── connection.py        # psycopg2 context manager
│   └── routers/
│       ├── auth.py              # POST /api/auth/login|register|logout|me
│       ├── movies.py            # GET  /api/movies, /api/movies/{id}/showtimes
│       ├── showtimes.py         # GET  /api/showtimes, /api/showtimes/{id}/seats
│       ├── bookings.py          # POST/GET/DELETE /api/bookings
│       ├── recommendations.py   # GET  /api/recommendations
│       └── admin.py             # GET/POST /api/admin/...
│
├── CineBook_Frontend/
│   ├── homepage.html            # Login + Register
│   ├── discoveryPage.html       # Movie catalog + recommendations
│   ├── seating.html             # Seat selection + booking
│   ├── userProfile.html         # Booking history + cancellation
│   ├── adminPage.html           # Forecasting dashboard + alerts
│   └── inventory.html           # Showtime management (admin)
│
├── database/
│   ├── schema.sql               # DDL: 7 tables, indexes, occupancy trigger
│   ├── seed.sql                 # Synthetic test data
│   └── recommendations_and_forecasting.sql  # Stored procs, triggers, views
│
├── scripts/
│   ├── init_db.py               # Create DB + apply schema
│   ├── seed_db.py               # Load seed data + hash passwords
│   └── fetch_tmdb.py            # Populate External_Metadata from TMDB API
│
├── tests/
│   └── test_api.py              # API validation tests
│
├── DEMO_SCRIPT.md               # Step-by-step demo walkthrough
├── .env                         # Environment variables (pre-configured)
└── requirements.txt
```

---

## API Endpoints (Summary)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /api/auth/login | — | Login → returns token |
| POST | /api/auth/register | — | Register new customer |
| GET | /api/auth/me | required | Current user info |
| GET | /api/movies | required | List all movies |
| GET | /api/movies/{id}/showtimes | required | Upcoming showtimes for movie |
| GET | /api/showtimes | required | All upcoming showtimes |
| GET | /api/showtimes/{id}/seats | required | Seat availability + dynamic price |
| POST | /api/bookings | required | Create booking |
| GET | /api/bookings/me | required | My booking history |
| DELETE | /api/bookings/{id} | required | Cancel booking |
| GET | /api/recommendations | customer | Personalized recommendations |
| GET | /api/admin/dashboard | admin | Forecast dashboard (mat. view) |
| GET | /api/admin/forecasts | admin | All forecast rows |
| POST | /api/admin/forecasts/run | admin | Run forecasting stored procedure |
| GET | /api/admin/alerts | admin | Admin capacity alerts |
| GET | /api/admin/showtimes | admin | Manage showtimes |
| POST | /api/admin/showtimes | admin | Create showtime |
| PUT | /api/admin/showtimes/{id} | admin | Update showtime price |
| GET | /api/admin/stats | admin | Summary statistics |

---

## Dynamic Pricing Rules

The pricing engine runs at booking time (`app/routers/bookings.py`):

| Condition | Effect |
|-----------|--------|
| Occupancy < 20% AND showtime < 2 hours away | **−15% discount** (last-minute deal) |
| Occupancy > 80% | **+15% surcharge** (high demand) |
| Otherwise | Standard base price |

This matches the rule described in the project report (Section 5.3).

---

## Key Database Features

- **`trg_update_occupancy`** — Auto-updates `Showtimes.CurrentOccupancy` on every booking INSERT/UPDATE
- **`trg_refresh_forecast`** — Auto-refreshes the `Demand_Forecasts` row after each booking
- **`trg_flag_high_demand`** — Creates `Admin_Alerts` when a showtime hits 70% or 90% capacity
- **`get_user_recommendations(user_id)`** — Returns ranked top-10 movies using genre, TMDB trending, and booking history
- **`run_demand_forecasting(admin_id)`** — Upserts forecasts using window functions (RANK, LAG, rolling AVG)
- **`mv_forecast_dashboard`** — Materialized view with `RANK()` and cumulative revenue
- **`mv_movie_performance`** — Materialized view with revenue share and genre rankings

---

## Environment Variables

| Variable | Default |
|---|---|
| DB_HOST | localhost |
| DB_PORT | 5432 |
| DB_NAME | cinebook |
| DB_USER | cinebook_user |
| DB_PASSWORD | DataDivas |
| TMDB_API_KEY | dd6aff4583f50a37c2fd453b95b7ab44 |
