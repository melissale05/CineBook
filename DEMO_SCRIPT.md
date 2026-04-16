# CineBook — Demo Script
### Database Systems, Stage 4 · Class Demo Walkthrough

---

## Setup Checklist (run before demo)

```bash
# Terminal 1: Start backend
cd CineBook
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Verify at: http://localhost:8000/health  →  {"status": "ok"}
# Swagger UI: http://localhost:8000/docs
```

Open `CineBook_Frontend/homepage.html` in browser (double-click or open via VS Code Live Server).

---

## FLOW A — Customer Journey (~5 minutes)

### Step 1: Register a new account
1. Open `homepage.html`
2. Fill out **Join the Elite** form (right side):
   - Name: `Demo User`
   - Email: `demo@test.com`
   - Password: `demo1234`
   - Favorite Genre: `Sci-Fi`
3. Click **Create Account**
4. Auto-redirected to `discoveryPage.html`

**Demonstrates:** `POST /api/auth/register` → bcrypt hash, session token, DB insert

---

### Step 2: Browse the movie catalog
1. On the discovery page:
   - Hero banner shows the top trending movie from the DB
   - **Top Picks for You** section shows your personalized recommendations (from `get_user_recommendations()` stored function)
   - **Movie Gallery** shows all 10 real movies from the DB with TMDB posters and ratings
2. Click a genre button in the left sidebar to filter movies
3. Type in the search bar to search movies in real time

**Demonstrates:** `GET /api/movies`, `GET /api/recommendations`, TMDB metadata

---

### Step 3: Select a movie and pick a showtime
1. Click any movie poster → navigates to `seating.html?showtime_id=X`
2. Left panel shows:
   - Real poster image, title, genre, runtime, description
   - TMDB rating
3. Showtime picker shows all upcoming showings with % fill bar

**Demonstrates:** `GET /api/movies/{id}/showtimes`, `GET /api/showtimes/{id}`

---

### Step 4: Book seats with dynamic pricing
1. In the seat map, click 2 seats to select them (yellow = selected)
2. Observe bottom bar update:
   - Ticket count updates
   - Total price calculates (may show discount or surcharge badge)
3. Click **Confirm Booking**
4. Success alert → redirected to `userProfile.html`

**Point out:** If a showtime is >80% full → +15% surcharge shown  
**Point out:** `trg_update_occupancy` trigger auto-increments `CurrentOccupancy`

**Demonstrates:** `POST /api/bookings`, dynamic pricing, DB trigger

---

### Step 5: View booking history + cancel
1. On `userProfile.html`:
   - User name and loyalty points pulled from DB
   - Booking table shows real bookings with status badges
2. Click **Cancel** on a confirmed upcoming booking
3. Row updates to "Cancelled"

**Demonstrates:** `GET /api/bookings/me`, `DELETE /api/bookings/{id}`, trigger decrements occupancy

---

## FLOW B — Admin Journey (~3 minutes)

### Step 6: Log in as admin
1. Navigate back to `homepage.html`
2. Login with:
   - Email: `admin@cinebook.com`
   - Password: `AdminPass!23`
3. Auto-redirected to `adminPage.html`

---

### Step 7: View the forecasting dashboard
1. **Stats cards** load at the top: total customers, bookings, revenue, upcoming shows, alerts
2. **Occupancy bar chart** shows real predicted fill % per showtime
3. **Forecast table** shows all Demand_Forecasts rows with:
   - Current fill % progress bars
   - Predicted occupancy and revenue
   - Recommendation level (add_screening, high_demand, adjust_price, normal)
4. Click **Run Forecasting Engine** button → calls `CALL run_demand_forecasting(admin_id)`
5. Table refreshes with new forecast data

**Point out:** Window functions — RANK(), LAG(), rolling 7-day AVG in the stored procedure  
**Point out:** Materialized view `mv_forecast_dashboard` with RANK() by date

**Demonstrates:** `POST /api/admin/forecasts/run`, `GET /api/admin/forecasts`

---

### Step 8: View and resolve alerts
1. Scroll down to **Smart Capacity Alerts**
2. Real alerts fired by `trg_flag_high_demand` trigger are shown
3. Click **Resolve** on an alert → updates `Admin_Alerts.Resolved = TRUE`

**Demonstrates:** `GET /api/admin/alerts`, `POST /api/admin/alerts/{id}/resolve`

---

### Step 9: Inventory management
1. Click **Inventory** in nav → `inventory.html`
2. Movie and theater dropdowns populate from DB
3. Fill out form → click **Add Showtime** → new row appears in table
4. Click **Edit Price** → enter new price → table updates

**Demonstrates:** `POST /api/admin/showtimes`, `PUT /api/admin/showtimes/{id}`

---

## FLOW C — Seed Account Demo (Role Differentiation)

Show how different customer genres get different recommendations:

```
alice@example.com / password123   →  Action recommendations
bob@example.com / password123     →  Horror recommendations  
david@example.com / password123   →  Sci-Fi recommendations
```

Log in as each and show the "Top Picks for You" section changes.

**Demonstrates:** `get_user_recommendations()` stored function — genre weighting, TMDB scoring, booking history exclusion

---

## Key SQL Features to Highlight During Demo

| Feature | Where visible |
|---------|---------------|
| `trg_update_occupancy` | Seat count updates instantly after booking |
| `trg_refresh_forecast` | Forecast row updates after booking |
| `trg_flag_high_demand` | New alert appears in admin panel for >70% shows |
| `get_user_recommendations()` | Top Picks section — genre/TMDB/booking-aware ranking |
| `run_demand_forecasting()` | Run Forecasting Engine button in admin |
| RANK() window function | RevenueRankOnDate in forecast dashboard |
| Dynamic pricing | Discount/surcharge badge on seating page |
| Role-based access | Admin navigates to dashboard; customer cannot |

---

## API Explorer (Swagger UI)

Open **http://localhost:8000/docs** to show the interactive API docs during demo.

Useful quick tests:
1. `POST /api/auth/login` with `{"email":"admin@cinebook.com","password":"AdminPass!23"}`
2. Copy the token → click **Authorize** → paste `Bearer <token>`
3. Call `GET /api/admin/forecasts` to show forecast data
4. Call `GET /api/recommendations` (as customer) to show ranked picks
