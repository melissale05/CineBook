"""
CineBook — API Validation Tests
Run: python tests/test_api.py  (requires server running on port 8000)

These tests validate the major API flows described in the project report:
  - Authentication (login, register)
  - Movie catalog
  - Showtime & seat queries
  - Booking creation + dynamic pricing
  - Booking cancellation
  - Recommendations (customer)
  - Admin forecasting flow
  - Role-based access control
"""

import sys
import requests

BASE = "http://localhost:8000/api"
PASS = "✓"
FAIL = "✗"

results = []

def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append((status, label, detail))
    print(f"  {status}  {label}" + (f"  → {detail}" if detail else ""))


def run():
    print("\n=== CineBook API Validation Tests ===\n")

    # ── Health ──────────────────────────────────────────────────────────────
    print("[ Health ]")
    try:
        r = requests.get(f"{BASE.replace('/api', '')}/health", timeout=3)
        check("Server is running", r.status_code == 200)
    except Exception:
        print(f"  {FAIL}  Server is NOT running on port 8000. Start with: uvicorn app.main:app --port 8000")
        sys.exit(1)

    # ── Auth: Login ─────────────────────────────────────────────────────────
    print("\n[ Authentication ]")
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@cinebook.com", "password": "AdminPass!23"})
    check("Admin login returns 200", r.status_code == 200, str(r.status_code))
    admin_token = r.json().get("token", "") if r.ok else ""
    check("Admin login returns token", bool(admin_token))
    check("Admin role is 'admin'", r.json().get("role") == "admin" if r.ok else False)

    r = requests.post(f"{BASE}/auth/login", json={"email": "alice@example.com", "password": "password123"})
    check("Customer login returns 200", r.status_code == 200)
    customer_token = r.json().get("token", "") if r.ok else ""
    check("Customer role is 'customer'", r.json().get("role") == "customer" if r.ok else False)
    check("Customer has favorite_genre", r.json().get("favorite_genre") is not None if r.ok else False)

    r_bad = requests.post(f"{BASE}/auth/login", json={"email": "admin@cinebook.com", "password": "wrongpassword"})
    check("Wrong password returns 401", r_bad.status_code == 401)

    def a_headers(tok): return {"Authorization": f"Bearer {tok}"}

    # ── Movies ───────────────────────────────────────────────────────────────
    print("\n[ Movie Catalog ]")
    r = requests.get(f"{BASE}/movies", headers=a_headers(customer_token))
    check("GET /movies returns 200", r.status_code == 200)
    movies = r.json() if r.ok else []
    check("Movie catalog has 10 movies", len(movies) == 10, f"got {len(movies)}")
    if movies:
        m = movies[0]
        check("Movie has poster_url", "poster_url" in m)
        check("Movie has tmdb_rating", "tmdb_rating" in m)
        check("Movie has description", "description" in m)

    r_genre = requests.get(f"{BASE}/movies?genre=Action", headers=a_headers(customer_token))
    check("Genre filter works", r_genre.status_code == 200)
    action_movies = r_genre.json() if r_genre.ok else []
    check("Action genre filter returns Action movies", all(m["genre"] == "Action" for m in action_movies))

    # ── Showtimes ────────────────────────────────────────────────────────────
    print("\n[ Showtimes ]")
    r = requests.get(f"{BASE}/showtimes", headers=a_headers(customer_token))
    check("GET /showtimes returns 200", r.status_code == 200)
    showtimes = r.json() if r.ok else []
    check("Showtimes list is not empty", len(showtimes) > 0, f"got {len(showtimes)}")

    if showtimes:
        st = showtimes[0]
        st_id = st["showtime_id"]
        check("Showtime has base_price", "base_price" in st)
        check("Showtime has final_price", "final_price" in st)
        check("Showtime has fill_pct", "fill_pct" in st)

        r_seats = requests.get(f"{BASE}/showtimes/{st_id}/seats", headers=a_headers(customer_token))
        check("GET /showtimes/{id}/seats returns 200", r_seats.status_code == 200)
        seats_data = r_seats.json() if r_seats.ok else {}
        check("Seats data has 'seats' list", "seats" in seats_data)
        check("Seats data has final_price", "final_price" in seats_data)

    # ── Recommendations ──────────────────────────────────────────────────────
    print("\n[ Recommendations ]")
    r = requests.get(f"{BASE}/recommendations", headers=a_headers(customer_token))
    check("GET /recommendations returns 200", r.status_code == 200)
    recs = r.json() if r.ok else []
    check("Recommendations list has entries", len(recs) > 0, f"got {len(recs)}")
    if recs:
        check("Recommendation has rank", "rank" in recs[0])
        check("Recommendation has recommendation_score", "recommendation_score" in recs[0])
        check("Recommendations are ranked ascending", recs[0]["rank"] <= recs[-1]["rank"])

    # Admin cannot get recommendations
    r_adm = requests.get(f"{BASE}/recommendations", headers=a_headers(admin_token))
    check("Admin cannot get customer recommendations (403)", r_adm.status_code == 403)

    # ── Booking ──────────────────────────────────────────────────────────────
    print("\n[ Booking ]")
    if showtimes:
        test_st_id = showtimes[0]["showtime_id"]
        # Find an available seat
        r_seats = requests.get(f"{BASE}/showtimes/{test_st_id}/seats", headers=a_headers(customer_token))
        available = [s["seat"] for s in r_seats.json().get("seats", []) if s["status"] == "available"]
        check("Available seats exist", len(available) > 0, f"{len(available)} available")

        if available:
            test_seat = available[0]
            r_book = requests.post(f"{BASE}/bookings", headers=a_headers(customer_token),
                                   json={"showtime_id": test_st_id, "seat_numbers": [test_seat]})
            check("POST /bookings returns 201", r_book.status_code == 201)
            booking_data = r_book.json() if r_book.ok else {}
            check("Booking has booking_ids", "booking_ids" in booking_data)
            check("Booking has final_price_per_seat", "final_price_per_seat" in booking_data)
            check("Booking has price_modifier", "price_modifier" in booking_data)
            new_booking_id = booking_data.get("booking_ids", [None])[0]

            # Verify seat is now taken
            r_seats2 = requests.get(f"{BASE}/showtimes/{test_st_id}/seats", headers=a_headers(customer_token))
            taken = [s["seat"] for s in r_seats2.json().get("seats", []) if s["status"] == "taken"]
            check(f"Seat {test_seat} is now taken (trigger fired)", test_seat in taken)

            # Duplicate booking should fail
            r_dup = requests.post(f"{BASE}/bookings", headers=a_headers(customer_token),
                                  json={"showtime_id": test_st_id, "seat_numbers": [test_seat]})
            check("Duplicate seat booking returns 409", r_dup.status_code == 409)

            # Cancel booking
            if new_booking_id:
                r_cancel = requests.delete(f"{BASE}/bookings/{new_booking_id}", headers=a_headers(customer_token))
                check("DELETE /bookings/{id} returns 200", r_cancel.status_code == 200)

    # My bookings
    r_mybookings = requests.get(f"{BASE}/bookings/me", headers=a_headers(customer_token))
    check("GET /bookings/me returns 200", r_mybookings.status_code == 200)

    # ── Admin ────────────────────────────────────────────────────────────────
    print("\n[ Admin Endpoints ]")
    r = requests.get(f"{BASE}/admin/stats", headers=a_headers(admin_token))
    check("GET /admin/stats returns 200", r.status_code == 200)
    stats = r.json() if r.ok else {}
    check("Stats has total_customers", "total_customers" in stats)
    check("Stats has total_revenue", "total_revenue" in stats)

    r = requests.get(f"{BASE}/admin/forecasts", headers=a_headers(admin_token))
    check("GET /admin/forecasts returns 200", r.status_code == 200)
    forecasts = r.json() if r.ok else []
    check("Forecasts list has entries", len(forecasts) > 0, f"got {len(forecasts)}")

    r_run = requests.post(f"{BASE}/admin/forecasts/run", headers=a_headers(admin_token))
    check("POST /admin/forecasts/run returns 200", r_run.status_code == 200)

    r = requests.get(f"{BASE}/admin/alerts", headers=a_headers(admin_token))
    check("GET /admin/alerts returns 200", r.status_code == 200)

    r = requests.get(f"{BASE}/admin/showtimes", headers=a_headers(admin_token))
    check("GET /admin/showtimes returns 200", r.status_code == 200)

    # ── Role-Based Access Control ────────────────────────────────────────────
    print("\n[ Role-Based Access Control ]")
    r = requests.get(f"{BASE}/admin/stats", headers=a_headers(customer_token))
    check("Customer cannot access /admin/stats (403)", r.status_code == 403)

    r = requests.get(f"{BASE}/admin/forecasts", headers=a_headers(customer_token))
    check("Customer cannot access /admin/forecasts (403)", r.status_code == 403)

    r = requests.get(f"{BASE}/movies")  # no auth
    check("Unauthenticated request returns 401 or 422", r.status_code in (401, 422))

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "="*45)
    passed = sum(1 for s, _, _ in results if s == PASS)
    failed = sum(1 for s, _, _ in results if s == FAIL)
    total  = passed + failed
    print(f"  Passed: {passed}/{total}")
    if failed:
        print(f"  Failed: {failed}/{total}")
        for s, label, detail in results:
            if s == FAIL:
                print(f"    {FAIL}  {label}" + (f"  ({detail})" if detail else ""))
    print("="*45 + "\n")
    return failed == 0


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
