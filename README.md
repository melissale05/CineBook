# CineBook

A web-based movie theater management and ticket booking application with dynamic demand pricing and smart recommendations.

**Course:** Database Systems
**Team:** Melissa Le · Fanta Amouzougan · Vanohra Gaspard

---

## Project Structure

```
CineBook/
├── app/                        # FastAPI application (Milestone 2+)
│   ├── core/
│   │   └── config.py           # Central settings (reads .env)
│   └── db/
│       └── connection.py       # psycopg2 connection helper / context manager
│
├── database/
│   ├── schema.sql              # Full DDL — all tables, indexes, triggers
│   └── seed.sql                # Synthetic data for development/testing
│
├── scripts/
│   ├── init_db.py              # Creates DB + applies schema  (run first)
│   ├── seed_db.py              # Loads seed.sql + hashes passwords
│   └── fetch_tmdb.py           # Fetches TMDB metadata → External_Metadata
│
├── .env.example                # Template — copy to .env and fill in values
├── requirements.txt
└── README.md
```

---

## Tech Stack

| Layer    | Technology                           |
|----------|--------------------------------------|
| Database | PostgreSQL 15+                       |
| Backend  | Python 3.11+ / FastAPI               |
| Frontend | React.js + HTML5/CSS3 (Milestone 4)  |
| External | TMDB API                             |

---

## Milestone Ownership

| Milestone | Owner              | Description                              |
|-----------|--------------------|------------------------------------------|
| 1         | All                | DB init, schema, seed data, TMDB fetch   |
| 2         | Melissa Le         | FastAPI routes, auth, CRUD endpoints     |
| 3         | Fanta Amouzougan   | Stored procedures, triggers, window fns  |
| 4         | Vanohra Gaspard    | React frontend, seating map, dashboards  |
| 5         | All                | Testing, documentation, final demo       |

---

## Milestone 1 Setup Guide

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ installed and running locally
- A [TMDB API key](https://www.themoviedb.org/settings/api) (free account) ** We already have the API key

### 1 — Clone and install dependencies

```bash
git clone <repo-url>
cd CineBook

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2 — Create a PostgreSQL user and configure .env

 Open the pgAdmin 4 app. Clcik on "servers" on the elft side bar and type password "DataDivas". Then click on Databses -> postgres -> query tool. Then run:

```sql
-- In psql as a superuser (e.g., postgres):
CREATE USER cinebook_user WITH PASSWORD 'your_secure_password';
ALTER USER cinebook_user CREATEDB;
```

```bash
cp .env.example .env
# Open .env and fill in DB_PASSWORD and TMDB_API_KEY (ALREADY DONE)
```

### 3 — Initialize the database
Open the project terminal and run: 
```bash
# Creates the 'cinebook' database and applies schema.sql
python scripts/init_db.py
```

### 4 — Load synthetic seed data
Open the project terminal and run: 
```bash
# Inserts test users, theaters, movies, showtimes, bookings, forecasts
python scripts/seed_db.py
```

### 5 — Populate live TMDB metadata
Open the project terminal and run: 
```bash
# Fetches popularity, rating, and trending status for each movie from TMDB
python scripts/fetch_tmdb.py
```

### Verify
 In pgAdmin4, go to servers -> PostgreSQL 18 -> databses. Right click databases and refresh. You will see the "Cinebook" database. Right click on cinebook, then on query tool and run: 
 
```sql
-- Connect to cinebook and run a quick sanity check
\c cinebook
SELECT m.Title, em.TMDB_Popularity, em.TMDB_Rating, em.TrendingStatus
FROM   Movies m
JOIN   External_Metadata em ON em.MovieID = m.MovieID
ORDER  BY em.TMDB_Popularity DESC;
```

---

## Database Schema

### Entities

| Table              | Primary Key   | Description                                         |
|--------------------|---------------|-----------------------------------------------------|
| `Users`            | UserID        | Customers and admins; stores bcrypt-hashed passwords|
| `Theaters`         | TheaterID     | Physical screening rooms (Hall A, IMAX, etc.)       |
| `Movies`           | MovieID       | Film catalog; links to TMDB via `TMDB_ID`           |
| `External_Metadata`| MetadataID    | Live TMDB data (popularity, rating, trending)       |
| `Showtimes`        | ShowtimeID    | A movie + theater + date/time + pricing slot        |
| `Bookings`         | BookingID     | One row per reserved seat                           |
| `Demand_Forecasts` | ForecastID    | Admin-facing predicted occupancy & revenue          |

### Key Relationships

```
Movies ──< Showtimes >── Theaters
Movies ──< External_Metadata
Showtimes ──< Bookings >── Users
Showtimes ──< Demand_Forecasts
```

### Automatic Triggers

- **`trg_update_occupancy`** — Updates `Showtimes.CurrentOccupancy` on every `Bookings` INSERT or status change, keeping the count consistent without requiring the application layer to manage it.

---

## Environment Variables

| Variable        | Description                             | Default            |
|-----------------|-----------------------------------------|--------------------|
| `DB_HOST`       | PostgreSQL host                         | `localhost`        |
| `DB_PORT`       | PostgreSQL port                         | `5432`             |
| `DB_NAME`       | Database name                           | `cinebook`         |
| `DB_USER`       | Database user                           | `cinebook_user`    |
| `DB_PASSWORD`   | Database password                       | *(required)*       |
| `TMDB_API_KEY`  | TMDB v3 API key                         | *(required)*       |
| `TMDB_BASE_URL` | TMDB base URL                           | `https://api.themoviedb.org/3` |

---

## Seed Test Accounts

| Email                  | Password       | Role     | Favorite Genre |
|------------------------|----------------|----------|----------------|
| admin@cinebook.com     | AdminPass!23   | admin    | —              |
| alice@example.com      | password123    | customer | Action         |
| bob@example.com        | password123    | customer | Horror         |
| david@example.com      | password123    | customer | Sci-Fi         |

> Passwords are bcrypt-hashed on seed load. Do **not** use these credentials in production.

---

## Notes for Team Members

- **Fanta (Database Lead, Milestone 3):** Stored procedures and window functions should be added as new `.sql` files under `database/` and called from the backend. The `get_db()` context manager in `app/db/connection.py` is ready for you to use.
- **Melissa (Backend Lead, Milestone 2):** FastAPI routes go in `app/routers/`. Use `app/db/connection.py`'s `get_db()` as a dependency. Auth should read `Users.Role` to implement role-based access.
- **Vanohra (Frontend Lead, Milestone 4):** The React app can live at `frontend/`. API responses from the FastAPI backend will be the data source for all UI components.
