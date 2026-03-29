-- =============================================================================
-- CineBook Database - Milestone 3
-- Advanced Engine: Smart Recommendation & Predictive Forecasting
-- PostgreSQL 15+
-- =============================================================================


-- =============================================================================
-- SECTION 1: STORED PROCEDURE — User Personalized Recommendations
-- Called after a Customer logs in.
-- Joins the user's FavoriteGenre + past booking history with live TMDB scores.
-- Returns a ranked "Top Picks" list unique to that user.
-- =============================================================================
DROP FUNCTION IF EXISTS get_user_recommendations(INTEGER) CASCADE;
DROP PROCEDURE IF EXISTS run_demand_forecasting(INTEGER) CASCADE;
DROP FUNCTION IF EXISTS refresh_forecast_on_booking() CASCADE;
DROP FUNCTION IF EXISTS flag_high_demand_showtime() CASCADE;
DROP FUNCTION IF EXISTS assert_role(INTEGER, VARCHAR) CASCADE;
CREATE OR REPLACE FUNCTION get_user_recommendations(p_user_id INTEGER)
RETURNS TABLE (
    MovieID       INTEGER,
    Title         VARCHAR(255),
    Genre         VARCHAR(100),
    TMDB_Rating   NUMERIC(3,1),
    TMDB_Popularity NUMERIC(10,3),
    TrendingStatus  VARCHAR(20),
    NextShowtime    TIMESTAMP,
    BasePrice       NUMERIC(8,2),
    RecommendationScore NUMERIC,
    Rank            BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER   -- runs with definer's privileges; callers cannot escalate
AS $$
DECLARE
    v_role          VARCHAR(20);
    v_fav_genre     VARCHAR(50);
BEGIN
    -- -------------------------------------------------------------------------
    -- Security: verify the calling user exists and is a customer
    -- -------------------------------------------------------------------------
    SELECT Role, FavoriteGenre
    INTO   v_role, v_fav_genre
    FROM   Users
    WHERE  UserID = p_user_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'User % not found.', p_user_id;
    END IF;

    IF v_role <> 'customer' THEN
        RAISE EXCEPTION 'Access denied: get_user_recommendations is for customers only.';
    END IF;

    -- -------------------------------------------------------------------------
    -- Core recommendation query
    -- Scoring logic (weights are tunable):
    --   +3.0  if movie genre matches user's FavoriteGenre
    --   +2.0  if movie is currently trending on TMDB
    --   +1.0  if user has booked this genre before (engagement signal)
    --   TMDB_Popularity / 100  continuous popularity boost
    --   TMDB_Rating / 2        quality boost (0-5 scale)
    -- Movies the user already has an active booking for are excluded.
    -- Only movies with at least one future showtime are returned.
    -- -------------------------------------------------------------------------
    RETURN QUERY
    WITH user_booked_genres AS (
        -- genres the user has historically engaged with
        SELECT DISTINCT m2.Genre AS booked_genre
        FROM   Bookings b2
        JOIN   Showtimes s2  ON b2.ShowtimeID = s2.ShowtimeID
        JOIN   Movies   m2  ON s2.MovieID     = m2.MovieID
        WHERE  b2.UserID = p_user_id
          AND  b2.Status = 'confirmed'
    ),
    already_booked AS (
        -- showtimes the user already holds a confirmed seat for
        SELECT DISTINCT s3.MovieID
        FROM   Bookings b3
        JOIN   Showtimes s3 ON b3.ShowtimeID = s3.ShowtimeID
        WHERE  b3.UserID = p_user_id
          AND  b3.Status = 'confirmed'
          AND  (s3.Date > CURRENT_DATE
                OR (s3.Date = CURRENT_DATE AND s3.StartTime > CURRENT_TIME))
    ),
    next_showtime AS (
        -- earliest upcoming showtime per movie
        SELECT  s4.MovieID,
                MIN(s4.Date + s4.StartTime) AS next_start,
                MIN(s4.BasePrice)           AS min_price
        FROM    Showtimes s4
        WHERE   s4.Date > CURRENT_DATE
           OR  (s4.Date = CURRENT_DATE AND s4.StartTime > CURRENT_TIME)
        GROUP BY s4.MovieID
    ),
    scored AS (
        SELECT
            m.MovieID,
            m.Title,
            m.Genre,
            em.TMDB_Rating,
            em.TMDB_Popularity,
            em.TrendingStatus,
            ns.next_start                               AS NextShowtime,
            ns.min_price                                AS BasePrice,
            -- composite recommendation score
            (
                CASE WHEN m.Genre = v_fav_genre            THEN 3.0 ELSE 0.0 END
              + CASE WHEN em.TrendingStatus = 'trending'   THEN 2.0 ELSE 0.0 END
              + CASE WHEN m.Genre IN (
                        SELECT booked_genre FROM user_booked_genres
                     )                                     THEN 1.0 ELSE 0.0 END
              + COALESCE(em.TMDB_Popularity, 0) / 100.0
              + COALESCE(em.TMDB_Rating,     0) / 2.0
            )::NUMERIC(8,3)                              AS RecommendationScore
        FROM   Movies        m
        JOIN   External_Metadata em ON m.MovieID = em.MovieID
        JOIN   next_showtime ns     ON m.MovieID = ns.MovieID
        -- exclude movies the user already has upcoming bookings for
        WHERE  m.MovieID NOT IN (SELECT MovieID FROM already_booked)
    )
    SELECT
        s.MovieID,
        s.Title,
        s.Genre,
        s.TMDB_Rating,
        s.TMDB_Popularity,
        s.TrendingStatus,
        s.NextShowtime,
        s.BasePrice,
        s.RecommendationScore,
        -- WINDOW FUNCTION: rank movies by score for this user
        RANK() OVER (ORDER BY s.RecommendationScore DESC) AS Rank
    FROM scored s
    ORDER BY Rank
    LIMIT 10;

END;
$$;


-- =============================================================================
-- SECTION 2: STORED PROCEDURE — Admin Predictive Demand Forecasting
-- Called after an Admin logs in.
-- Uses window functions over historical Bookings + Showtimes to predict
-- future occupancy and revenue, then writes results to Demand_Forecasts.
-- =============================================================================

CREATE OR REPLACE PROCEDURE run_demand_forecasting(p_admin_id INTEGER)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_role VARCHAR(20);
BEGIN
    -- -------------------------------------------------------------------------
    -- Security: only admins may run the forecasting engine
    -- -------------------------------------------------------------------------
    SELECT Role INTO v_role
    FROM   Users
    WHERE  UserID = p_admin_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'User % not found.', p_admin_id;
    END IF;

    IF v_role <> 'admin' THEN
        RAISE EXCEPTION 'Access denied: run_demand_forecasting is for admins only.';
    END IF;

    -- -------------------------------------------------------------------------
    -- Forecasting logic
    --
    -- For every future showtime we calculate:
    --   avg_historical_fill_rate : average fill % for (movie, day-of-week) pairs
    --                              over the last 90 days using a window function
    --   tmdb_popularity_boost    : scales the fill rate up for trending movies
    --   predicted_occupancy      : capped at 100%
    --   predicted_revenue        : predicted seats * BasePrice
    --   recommendation_level     : action flag for the admin dashboard
    --
    -- Window function used: AVG(...) OVER (PARTITION BY movie, dow)
    -- -------------------------------------------------------------------------
    INSERT INTO Demand_Forecasts
        (ShowtimeID, PredictedOccupancy, PredictedRevenue, RecommendationLevel, GeneratedAt)

    WITH historical_fill AS (
        -- one row per past showtime with its actual fill percentage
        SELECT
            s.ShowtimeID,
            s.MovieID,
            s.TheaterID,
            EXTRACT(DOW FROM s.Date)                        AS day_of_week,
            s.TotalCapacity,
            s.CurrentOccupancy,
            CASE WHEN t.TotalCapacity > 0
                 THEN (s.CurrentOccupancy::NUMERIC / t.TotalCapacity) * 100
                 ELSE 0
            END                                              AS fill_pct
        FROM  Showtimes s
        JOIN  Theaters  t ON s.TheaterID = t.TheaterID
        WHERE s.Date < CURRENT_DATE          -- only past showtimes
          AND s.Date >= CURRENT_DATE - 90    -- rolling 90-day window
    ),
    avg_fill_by_movie_dow AS (
        -- WINDOW FUNCTION: average fill rate per (movie, day-of-week)
        -- partitioned so each movie/day combo gets its own baseline
        SELECT DISTINCT
            MovieID,
            day_of_week,
            AVG(fill_pct) OVER (
                PARTITION BY MovieID, day_of_week
            )::NUMERIC(5,2)  AS avg_fill_pct,
            -- also rank how "popular" each day is for this movie
            RANK() OVER (
                PARTITION BY MovieID
                ORDER BY AVG(fill_pct) OVER (PARTITION BY MovieID, day_of_week) DESC
            )                 AS day_popularity_rank
        FROM historical_fill
    ),
    revenue_trend AS (
        -- WINDOW FUNCTION: rolling 7-day average confirmed revenue per movie
        -- gives us a revenue velocity signal
        SELECT
            s.MovieID,
            SUM(b.FinalPrice)  AS daily_revenue,
            s.Date,
            AVG(SUM(b.FinalPrice)) OVER (
                PARTITION BY s.MovieID
                ORDER BY s.Date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            )::NUMERIC(12,2)   AS rolling_7day_avg_revenue
        FROM  Bookings  b
        JOIN  Showtimes s ON b.ShowtimeID = s.ShowtimeID
        WHERE b.Status = 'confirmed'
          AND s.Date  >= CURRENT_DATE - 30
        GROUP BY s.MovieID, s.Date
    ),
    future_showtimes AS (
        -- showtimes we need to forecast
        SELECT
            s.ShowtimeID,
            s.MovieID,
            s.TheaterID,
            s.Date,
            s.BasePrice,
            t.TotalCapacity,
            EXTRACT(DOW FROM s.Date)            AS day_of_week,
            COALESCE(em.TMDB_Popularity, 50)    AS popularity,
            em.TrendingStatus
        FROM  Showtimes          s
        JOIN  Theaters           t  ON s.TheaterID = t.TheaterID
        LEFT JOIN External_Metadata em ON s.MovieID = em.MovieID
        WHERE s.Date >= CURRENT_DATE
    ),
    forecast_calc AS (
        SELECT
            fs.ShowtimeID,
            fs.TotalCapacity,
            fs.BasePrice,
            fs.TrendingStatus,
            -- base fill rate from history (default 40% if no history yet)
            COALESCE(af.avg_fill_pct, 40.0)     AS base_fill_pct,
            -- popularity multiplier: trending = +20%, declining = -10%, normal = 0
            CASE fs.TrendingStatus
                WHEN 'trending'  THEN 1.20
                WHEN 'declining' THEN 0.90
                ELSE                  1.00
            END                                  AS trend_multiplier,
            -- recency revenue signal (if recent revenue velocity is high, boost)
            CASE WHEN rt.rolling_7day_avg_revenue > 500 THEN 1.10
                 WHEN rt.rolling_7day_avg_revenue > 200 THEN 1.05
                 ELSE 1.00
            END                                  AS revenue_velocity_boost
        FROM  future_showtimes fs
        LEFT JOIN avg_fill_by_movie_dow af
               ON fs.MovieID = af.MovieID AND fs.day_of_week = af.day_of_week
        LEFT JOIN revenue_trend rt
               ON fs.MovieID = rt.MovieID AND rt.Date = (
                   -- use most recent revenue record for this movie
                   SELECT MAX(Date) FROM revenue_trend rt2
                   WHERE rt2.MovieID = fs.MovieID
               )
    ),
    final_forecast AS (
        SELECT
            fc.ShowtimeID,
            -- cap predicted occupancy at 100%
            LEAST(
                fc.base_fill_pct * fc.trend_multiplier * fc.revenue_velocity_boost,
                100.0
            )::NUMERIC(5,2)                      AS predicted_occ_pct,
            fc.TotalCapacity,
            fc.BasePrice,
            fc.TrendingStatus
        FROM forecast_calc fc
    )
    SELECT
        ff.ShowtimeID,
        ff.predicted_occ_pct                     AS PredictedOccupancy,
        -- PredictedRevenue = predicted seats filled * base ticket price
        ROUND(
            (ff.predicted_occ_pct / 100.0) * ff.TotalCapacity * ff.BasePrice,
            2
        )                                        AS PredictedRevenue,
        -- Action recommendation for admin dashboard
        CASE
            WHEN ff.predicted_occ_pct >= 90 THEN 'add_screening'
            WHEN ff.predicted_occ_pct >= 70 THEN 'high_demand'
            WHEN ff.predicted_occ_pct >= 50 AND ff.TrendingStatus = 'trending'
                                             THEN 'adjust_price'
            ELSE                                  'normal'
        END                                      AS RecommendationLevel,
        NOW()                                    AS GeneratedAt
    FROM final_forecast ff

    -- UPSERT: update existing forecast rows instead of duplicating
    ON CONFLICT (ShowtimeID)
    DO UPDATE SET
        PredictedOccupancy  = EXCLUDED.PredictedOccupancy,
        PredictedRevenue    = EXCLUDED.PredictedRevenue,
        RecommendationLevel = EXCLUDED.RecommendationLevel,
        GeneratedAt         = EXCLUDED.GeneratedAt;

    RAISE NOTICE 'Forecasting complete. Forecasts refreshed for all future showtimes.';
END;
$$;

-- Make the ON CONFLICT clause work: Demand_Forecasts needs a unique constraint on ShowtimeID

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_forecast_showtime'
    ) THEN
        ALTER TABLE Demand_Forecasts
            ADD CONSTRAINT uq_forecast_showtime UNIQUE (ShowtimeID);
    END IF;
END;
$$;

-- =============================================================================
-- SECTION 3: TRIGGER — Auto-refresh forecast when a new booking is confirmed
-- After every INSERT/UPDATE on Bookings, if the showtime's fill rate crosses
-- the 70% threshold, the forecast row is updated and flagged for the admin.
-- This is a lightweight per-row trigger (not a full re-run of the procedure).
-- =============================================================================

CREATE OR REPLACE FUNCTION refresh_forecast_on_booking()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_capacity      INTEGER;
    v_occupancy     INTEGER;
    v_fill_pct      NUMERIC(5,2);
    v_base_price    NUMERIC(8,2);
    v_rec_level     VARCHAR(20);
BEGIN
    -- Only react to confirmed bookings
    IF NEW.Status <> 'confirmed' THEN
        RETURN NEW;
    END IF;

    -- Fetch current showtime state
    SELECT t.TotalCapacity, s.CurrentOccupancy, s.BasePrice
    INTO   v_capacity, v_occupancy, v_base_price
    FROM   Showtimes s
    JOIN   Theaters  t ON s.TheaterID = t.TheaterID
    WHERE  s.ShowtimeID = NEW.ShowtimeID;

    IF NOT FOUND THEN
        RETURN NEW;
    END IF;

    -- Calculate current fill percentage
    v_fill_pct := CASE WHEN v_capacity > 0
                       THEN (v_occupancy::NUMERIC / v_capacity) * 100
                       ELSE 0
                  END;

    -- Determine recommendation level based on live fill %
    v_rec_level := CASE
                        WHEN v_fill_pct >= 90 THEN 'add_screening'
                        WHEN v_fill_pct >= 70 THEN 'high_demand'
                        ELSE                       'normal'
                   END;

    -- Upsert into Demand_Forecasts (lightweight update, not full forecast run)
    INSERT INTO Demand_Forecasts
        (ShowtimeID, PredictedOccupancy, PredictedRevenue, RecommendationLevel, GeneratedAt)
    VALUES (
        NEW.ShowtimeID,
        v_fill_pct,
        ROUND((v_fill_pct / 100.0) * v_capacity * v_base_price, 2),
        v_rec_level,
        NOW()
    )
    ON CONFLICT (ShowtimeID)
    DO UPDATE SET
        PredictedOccupancy  = EXCLUDED.PredictedOccupancy,
        PredictedRevenue    = EXCLUDED.PredictedRevenue,
        RecommendationLevel = EXCLUDED.RecommendationLevel,
        GeneratedAt         = EXCLUDED.GeneratedAt;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_refresh_forecast ON Bookings;
CREATE TRIGGER trg_refresh_forecast
AFTER INSERT OR UPDATE OF Status ON Bookings
FOR EACH ROW EXECUTE FUNCTION refresh_forecast_on_booking();


-- =============================================================================
-- SECTION 4: TRIGGER — Flag "High Demand" showtimes for admin alerts
-- Fires when CurrentOccupancy is updated on Showtimes (driven by the
-- existing trg_update_occupancy trigger in Milestone 1).
-- Inserts a notification-style record if occupancy crosses 70%.
-- =============================================================================

-- Admin alert log table (lightweight, separate from forecasts)
CREATE TABLE IF NOT EXISTS Admin_Alerts (
    AlertID     SERIAL PRIMARY KEY,
    ShowtimeID  INTEGER NOT NULL REFERENCES Showtimes(ShowtimeID) ON DELETE CASCADE,
    AlertType   VARCHAR(50) NOT NULL,
    Message     TEXT,
    CreatedAt   TIMESTAMP NOT NULL DEFAULT NOW(),
    Resolved    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_alerts_showtime ON Admin_Alerts(ShowtimeID);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON Admin_Alerts(Resolved);

CREATE OR REPLACE FUNCTION flag_high_demand_showtime()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_capacity   INTEGER;
    v_fill_pct   NUMERIC(5,2);
    v_title      VARCHAR(255);
    v_date       DATE;
    v_time       TIME;
BEGIN
    -- Only act if occupancy actually changed
    IF NEW.CurrentOccupancy = OLD.CurrentOccupancy THEN
        RETURN NEW;
    END IF;

    SELECT t.TotalCapacity INTO v_capacity
    FROM   Theaters t
    WHERE  t.TheaterID = NEW.TheaterID;

    v_fill_pct := CASE WHEN v_capacity > 0
                       THEN (NEW.CurrentOccupancy::NUMERIC / v_capacity) * 100
                       ELSE 0
                  END;

    -- Fetch movie title for the alert message
    SELECT m.Title, NEW.Date, NEW.StartTime
    INTO   v_title, v_date, v_time
    FROM   Movies m
    WHERE  m.MovieID = NEW.MovieID;

    -- Alert at 70% threshold (high demand)
    IF v_fill_pct >= 70 AND
       (OLD.CurrentOccupancy::NUMERIC / v_capacity) * 100 < 70 THEN
        INSERT INTO Admin_Alerts (ShowtimeID, AlertType, Message)
        VALUES (
            NEW.ShowtimeID,
            'high_demand',
            FORMAT('"%s" on %s at %s has reached %s%% capacity. Consider adding a screening.',
                   v_title, v_date, v_time, ROUND(v_fill_pct, 1))
        );
    END IF;

    -- Additional alert at 90% threshold (near sold-out)
    IF v_fill_pct >= 90 AND
       (OLD.CurrentOccupancy::NUMERIC / v_capacity) * 100 < 90 THEN
        INSERT INTO Admin_Alerts (ShowtimeID, AlertType, Message)
        VALUES (
            NEW.ShowtimeID,
            'near_sold_out',
            FORMAT('"%s" on %s at %s is %s%% full — nearly sold out!',
                   v_title, v_date, v_time, ROUND(v_fill_pct, 1))
        );
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_flag_high_demand ON Showtimes;
CREATE TRIGGER trg_flag_high_demand
AFTER UPDATE OF CurrentOccupancy ON Showtimes
FOR EACH ROW EXECUTE FUNCTION flag_high_demand_showtime();


-- =============================================================================
-- SECTION 5: ADMIN DASHBOARD VIEWS
-- Materialized views that power the admin analytics dashboard without
-- running heavy queries on every page load.
-- =============================================================================

-- View 1: Full forecast summary for the admin dashboard
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_forecast_dashboard AS
SELECT
    df.ForecastID,
    df.ShowtimeID,
    m.Title                                          AS MovieTitle,
    m.Genre,
    s.Date                                           AS ShowDate,
    s.StartTime,
    th.Name                                          AS TheaterName,
    'Standard' AS ScreenType,
    s.BasePrice,
    th.TotalCapacity,
    s.CurrentOccupancy,
    ROUND((s.CurrentOccupancy::NUMERIC / th.TotalCapacity) * 100, 1)
                                                     AS CurrentFillPct,
    df.PredictedOccupancy,
    df.PredictedRevenue,
    df.RecommendationLevel,
    NOW() AS GeneratedAt,
    em.TMDB_Rating,
    em.TMDB_Popularity,
    em.TrendingStatus,
    -- WINDOW FUNCTION: rank showtimes by predicted revenue within each date
    RANK() OVER (
        PARTITION BY s.Date
        ORDER BY df.PredictedRevenue DESC NULLS LAST
    )                                                AS RevenueRankOnDate,
    -- WINDOW FUNCTION: running total of predicted revenue per movie
    SUM(df.PredictedRevenue) OVER (
        PARTITION BY m.MovieID
        ORDER BY s.Date, s.StartTime
        ROWS UNBOUNDED PRECEDING
    )                                                AS CumulativePredictedRevenue
FROM  Demand_Forecasts df
JOIN  Showtimes          s   ON df.ShowtimeID  = s.ShowtimeID
JOIN  Movies             m   ON s.MovieID      = m.MovieID
JOIN  Theaters           th  ON s.TheaterID    = th.TheaterID
LEFT JOIN External_Metadata em ON m.MovieID    = em.MovieID
WITH NO DATA;  -- populated on first REFRESH

-- Refresh the materialized view (call this after run_demand_forecasting())
-- REFRESH MATERIALIZED VIEW mv_forecast_dashboard;


-- View 2: Top performing movies by booking velocity (last 30 days)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_movie_performance AS
SELECT
    m.MovieID,
    m.Title,
    m.Genre,
    COUNT(b.BookingID)                               AS TotalBookings,
    SUM(b.FinalPrice)                                AS TotalRevenue,
    AVG(b.FinalPrice)                                AS AvgTicketPrice,
    COUNT(DISTINCT b.UserID)                         AS UniqueCustomers,
    -- WINDOW FUNCTION: rank by total revenue in their genre
    RANK() OVER (
        PARTITION BY m.Genre
        ORDER BY SUM(b.FinalPrice) DESC NULLS LAST
    )                                                AS RevenueRankInGenre,
    -- WINDOW FUNCTION: percent of total revenue this movie represents
    ROUND(
        SUM(b.FinalPrice) / NULLIF(
            SUM(SUM(b.FinalPrice)) OVER (), 0
        ) * 100, 2
    )                                                AS RevenueSharePct
FROM  Movies    m
JOIN  Showtimes s  ON m.MovieID    = s.MovieID
JOIN  Bookings  b  ON s.ShowtimeID = b.ShowtimeID
WHERE b.Status     = 'confirmed'
  AND b.BookingTime >= NOW() - INTERVAL '30 days'
GROUP BY m.MovieID, m.Title, m.Genre
WITH NO DATA;


-- =============================================================================
-- SECTION 6: HELPER — Role-based access guard function
-- Call this at the start of any sensitive query to enforce access control.
-- Usage: PERFORM assert_role(p_user_id, 'admin');
-- =============================================================================

CREATE OR REPLACE FUNCTION assert_role(p_user_id INTEGER, p_required_role VARCHAR)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_role VARCHAR(20);
BEGIN
    SELECT Role INTO v_role FROM Users WHERE UserID = p_user_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'User % does not exist.', p_user_id;
    END IF;
    IF v_role <> p_required_role THEN
        RAISE EXCEPTION 'Access denied: requires role "%" but user has role "%".',
            p_required_role, v_role;
    END IF;
END;
$$;


-- =============================================================================
-- SECTION 7: GRANTS
-- Restrict who can call sensitive procedures from the application layer.
-- Replace 'cinebook_app' with your actual application DB user.
-- =============================================================================

-- GRANT EXECUTE ON FUNCTION  get_user_recommendations(INTEGER) TO cinebook_app;
-- GRANT EXECUTE ON PROCEDURE run_demand_forecasting(INTEGER)    TO cinebook_app;
-- GRANT EXECUTE ON FUNCTION  assert_role(INTEGER, VARCHAR)      TO cinebook_app;
-- REVOKE ALL ON TABLE Demand_Forecasts FROM cinebook_app;  -- app reads via views only
-- GRANT SELECT ON mv_forecast_dashboard  TO cinebook_app;
-- GRANT SELECT ON mv_movie_performance   TO cinebook_app;
