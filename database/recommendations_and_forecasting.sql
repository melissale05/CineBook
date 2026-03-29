-- CineBook - Advanced Engine: Smart Recommendation & Predictive Forecasting
-- Milestone 3 | PostgreSQL 15+
-- Run after schema.sql and seed.sql

-- Drop existing functions/procedures/triggers before recreating
DROP FUNCTION  IF EXISTS get_user_recommendations(INTEGER) CASCADE;
DROP PROCEDURE IF EXISTS run_demand_forecasting(INTEGER) CASCADE;
DROP FUNCTION  IF EXISTS refresh_forecast_on_booking() CASCADE;
DROP FUNCTION  IF EXISTS flag_high_demand_showtime() CASCADE;
DROP FUNCTION  IF EXISTS assert_role(INTEGER, VARCHAR) CASCADE;


-- -------------------------------------------------------------------------
-- 1. USER RECOMMENDATION ENGINE
-- Returns a ranked top-10 movie list personalized for a logged-in customer.
-- Scores are based on genre preference, TMDB trending status, booking history,
-- popularity, and rating. Excludes movies the user already booked.
-- -------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION get_user_recommendations(p_user_id INTEGER)
RETURNS TABLE (
    MovieID             INTEGER,
    Title               VARCHAR(255),
    Genre               VARCHAR(100),
    TMDB_Rating         NUMERIC(3,1),
    TMDB_Popularity     NUMERIC(10,3),
    TrendingStatus      VARCHAR(20),
    NextShowtime        TIMESTAMP,
    BasePrice           NUMERIC(8,2),
    RecommendationScore NUMERIC,
    Rank                BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_role      VARCHAR(20);
    v_fav_genre VARCHAR(50);
BEGIN
    -- Verify user exists and is a customer
    SELECT Role, FavoriteGenre
    INTO   v_role, v_fav_genre
    FROM   Users
    WHERE  UserID = p_user_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'User % not found.', p_user_id;
    END IF;

    IF v_role <> 'customer' THEN
        RAISE EXCEPTION 'Access denied: only customers can get recommendations.';
    END IF;

    RETURN QUERY
    WITH user_booked_genres AS (
        -- genres this user has previously booked
        SELECT DISTINCT m2.Genre AS booked_genre
        FROM   Bookings  b2
        JOIN   Showtimes s2 ON b2.ShowtimeID = s2.ShowtimeID
        JOIN   Movies    m2 ON s2.MovieID    = m2.MovieID
        WHERE  b2.UserID = p_user_id
          AND  b2.Status = 'confirmed'
    ),
    already_booked AS (
        -- movies the user already has an upcoming confirmed booking for
        SELECT DISTINCT s3.MovieID
        FROM   Bookings  b3
        JOIN   Showtimes s3 ON b3.ShowtimeID = s3.ShowtimeID
        WHERE  b3.UserID = p_user_id
          AND  b3.Status = 'confirmed'
          AND  (s3.Date > CURRENT_DATE
                OR (s3.Date = CURRENT_DATE AND s3.StartTime > CURRENT_TIME))
    ),
    next_showtime AS (
        -- earliest upcoming showtime and lowest price per movie
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
            ns.next_start AS NextShowtime,
            ns.min_price  AS BasePrice,
            -- scoring: +3 favorite genre, +2 trending, +1 past genre, +popularity/rating boost
            (
                CASE WHEN m.Genre = v_fav_genre          THEN 3.0 ELSE 0.0 END
              + CASE WHEN em.TrendingStatus = 'trending' THEN 2.0 ELSE 0.0 END
              + CASE WHEN m.Genre IN (
                        SELECT booked_genre FROM user_booked_genres
                     )                                   THEN 1.0 ELSE 0.0 END
              + COALESCE(em.TMDB_Popularity, 0) / 100.0
              + COALESCE(em.TMDB_Rating,     0) / 2.0
            )::NUMERIC(8,3) AS RecommendationScore
        FROM   Movies            m
        JOIN   External_Metadata em ON m.MovieID = em.MovieID
        JOIN   next_showtime     ns ON m.MovieID = ns.MovieID
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
        -- rank movies from highest to lowest score
        RANK() OVER (ORDER BY s.RecommendationScore DESC) AS Rank
    FROM scored s
    ORDER BY Rank
    LIMIT 10;

END;
$$;


-- -------------------------------------------------------------------------
-- 2. ADMIN DEMAND FORECASTING ENGINE
-- Predicts future showtime occupancy and revenue using historical fill rates,
-- TMDB trending data, and recent booking velocity.
-- Results are written to the Demand_Forecasts table.
-- -------------------------------------------------------------------------

CREATE OR REPLACE PROCEDURE run_demand_forecasting(p_admin_id INTEGER)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_role VARCHAR(20);
BEGIN
    -- Only admins can run the forecasting engine
    SELECT Role INTO v_role
    FROM   Users
    WHERE  UserID = p_admin_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'User % not found.', p_admin_id;
    END IF;

    IF v_role <> 'admin' THEN
        RAISE EXCEPTION 'Access denied: only admins can run demand forecasting.';
    END IF;

    INSERT INTO Demand_Forecasts
        (ShowtimeID, PredictedOccupancy, PredictedRevenue, RecommendationLevel, GeneratedAt)

    WITH historical_fill AS (
        -- calculate actual fill % for each past showtime (last 90 days)
        SELECT
            s.ShowtimeID,
            s.MovieID,
            s.TheaterID,
            EXTRACT(DOW FROM s.Date) AS day_of_week,
            t.TotalCapacity,
            s.CurrentOccupancy,
            CASE WHEN t.TotalCapacity > 0
                 THEN (s.CurrentOccupancy::NUMERIC / t.TotalCapacity) * 100
                 ELSE 0
            END AS fill_pct
        FROM  Showtimes s
        JOIN  Theaters  t ON s.TheaterID = t.TheaterID
        WHERE s.Date < CURRENT_DATE
          AND s.Date >= CURRENT_DATE - 90
    ),
    avg_fill_by_movie_dow AS (
        -- window function: average fill rate per movie per day of week
        SELECT DISTINCT
            MovieID,
            day_of_week,
            AVG(fill_pct) OVER (
                PARTITION BY MovieID, day_of_week
            )::NUMERIC(5,2) AS avg_fill_pct,
            RANK() OVER (
                PARTITION BY MovieID
                ORDER BY AVG(fill_pct) OVER (PARTITION BY MovieID, day_of_week) DESC
            ) AS day_popularity_rank
        FROM historical_fill
    ),
    revenue_trend AS (
        -- window function: 7-day rolling average revenue per movie
        SELECT
            s.MovieID,
            s.Date,
            SUM(b.FinalPrice) AS daily_revenue,
            AVG(SUM(b.FinalPrice)) OVER (
                PARTITION BY s.MovieID
                ORDER BY s.Date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            )::NUMERIC(12,2) AS rolling_7day_avg_revenue
        FROM  Bookings  b
        JOIN  Showtimes s ON b.ShowtimeID = s.ShowtimeID
        WHERE b.Status = 'confirmed'
          AND s.Date  >= CURRENT_DATE - 30
        GROUP BY s.MovieID, s.Date
    ),
    future_showtimes AS (
        -- all upcoming showtimes that need a forecast
        SELECT
            s.ShowtimeID,
            s.MovieID,
            s.TheaterID,
            s.Date,
            s.BasePrice,
            t.TotalCapacity,
            EXTRACT(DOW FROM s.Date)         AS day_of_week,
            COALESCE(em.TMDB_Popularity, 50) AS popularity,
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
            COALESCE(af.avg_fill_pct, 40.0) AS base_fill_pct,
            -- trending movies get a boost, declining ones get a penalty
            CASE fs.TrendingStatus
                WHEN 'trending'  THEN 1.20
                WHEN 'declining' THEN 0.90
                ELSE                  1.00
            END AS trend_multiplier,
            -- boost if recent revenue velocity is high
            CASE WHEN rt.rolling_7day_avg_revenue > 500 THEN 1.10
                 WHEN rt.rolling_7day_avg_revenue > 200 THEN 1.05
                 ELSE 1.00
            END AS revenue_velocity_boost
        FROM  future_showtimes fs
        LEFT JOIN avg_fill_by_movie_dow af
               ON fs.MovieID = af.MovieID AND fs.day_of_week = af.day_of_week
        LEFT JOIN revenue_trend rt
               ON fs.MovieID = rt.MovieID AND rt.Date = (
                   SELECT MAX(Date) FROM revenue_trend rt2
                   WHERE rt2.MovieID = fs.MovieID
               )
    ),
    final_forecast AS (
        SELECT
            fc.ShowtimeID,
            LEAST(
                fc.base_fill_pct * fc.trend_multiplier * fc.revenue_velocity_boost,
                100.0
            )::NUMERIC(5,2) AS predicted_occ_pct,
            fc.TotalCapacity,
            fc.BasePrice,
            fc.TrendingStatus
        FROM forecast_calc fc
    )
    SELECT
        ff.ShowtimeID,
        ff.predicted_occ_pct AS PredictedOccupancy,
        ROUND(
            (ff.predicted_occ_pct / 100.0) * ff.TotalCapacity * ff.BasePrice, 2
        ) AS PredictedRevenue,
        CASE
            WHEN ff.predicted_occ_pct >= 90 THEN 'add_screening'
            WHEN ff.predicted_occ_pct >= 70 THEN 'high_demand'
            WHEN ff.predicted_occ_pct >= 50 AND ff.TrendingStatus = 'trending'
                                             THEN 'adjust_price'
            ELSE                                  'normal'
        END AS RecommendationLevel,
        NOW() AS GeneratedAt
    FROM final_forecast ff

    ON CONFLICT (ShowtimeID)
    DO UPDATE SET
        PredictedOccupancy  = EXCLUDED.PredictedOccupancy,
        PredictedRevenue    = EXCLUDED.PredictedRevenue,
        RecommendationLevel = EXCLUDED.RecommendationLevel,
        GeneratedAt         = EXCLUDED.GeneratedAt;

    RAISE NOTICE 'Forecasting complete.';
END;
$$;

-- Unique constraint needed for the upsert above
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_forecast_showtime'
    ) THEN
        ALTER TABLE Demand_Forecasts
            ADD CONSTRAINT uq_forecast_showtime UNIQUE (ShowtimeID);
    END IF;
END;
$$;


-- -------------------------------------------------------------------------
-- 3. TRIGGER: Auto-update forecast when a booking is confirmed
-- Runs after every confirmed booking and refreshes that showtime's forecast row.
-- -------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION refresh_forecast_on_booking()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_capacity   INTEGER;
    v_occupancy  INTEGER;
    v_fill_pct   NUMERIC(5,2);
    v_base_price NUMERIC(8,2);
    v_rec_level  VARCHAR(20);
BEGIN
    IF NEW.Status <> 'confirmed' THEN
        RETURN NEW;
    END IF;

    SELECT t.TotalCapacity, s.CurrentOccupancy, s.BasePrice
    INTO   v_capacity, v_occupancy, v_base_price
    FROM   Showtimes s
    JOIN   Theaters  t ON s.TheaterID = t.TheaterID
    WHERE  s.ShowtimeID = NEW.ShowtimeID;

    IF NOT FOUND THEN
        RETURN NEW;
    END IF;

    v_fill_pct := CASE WHEN v_capacity > 0
                       THEN (v_occupancy::NUMERIC / v_capacity) * 100
                       ELSE 0
                  END;

    v_rec_level := CASE
                       WHEN v_fill_pct >= 90 THEN 'add_screening'
                       WHEN v_fill_pct >= 70 THEN 'high_demand'
                       ELSE                       'normal'
                   END;

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


-- -------------------------------------------------------------------------
-- 4. TRIGGER: Flag high-demand showtimes for admin alerts
-- Fires when CurrentOccupancy changes. Inserts an alert at 70% and 90% capacity.
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Admin_Alerts (
    AlertID    SERIAL PRIMARY KEY,
    ShowtimeID INTEGER NOT NULL REFERENCES Showtimes(ShowtimeID) ON DELETE CASCADE,
    AlertType  VARCHAR(50) NOT NULL,
    Message    TEXT,
    CreatedAt  TIMESTAMP NOT NULL DEFAULT NOW(),
    Resolved   BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_alerts_showtime ON Admin_Alerts(ShowtimeID);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON Admin_Alerts(Resolved);

CREATE OR REPLACE FUNCTION flag_high_demand_showtime()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_capacity INTEGER;
    v_fill_pct NUMERIC(5,2);
    v_title    VARCHAR(255);
    v_date     DATE;
    v_time     TIME;
BEGIN
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

    SELECT m.Title, NEW.Date, NEW.StartTime
    INTO   v_title, v_date, v_time
    FROM   Movies m
    WHERE  m.MovieID = NEW.MovieID;

    -- alert when showtime crosses 70% capacity
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

    -- alert when showtime crosses 90% capacity
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


-- -------------------------------------------------------------------------
-- 5. ADMIN DASHBOARD VIEWS
-- Materialized views so the admin dashboard loads fast without re-running
-- heavy queries every time. Refresh after running the forecasting procedure.
-- -------------------------------------------------------------------------

-- Full forecast dashboard with revenue rankings per date
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_forecast_dashboard AS
SELECT
    df.ForecastID,
    df.ShowtimeID,
    m.Title                                                              AS MovieTitle,
    m.Genre,
    s.Date                                                               AS ShowDate,
    s.StartTime,
    th.Name                                                              AS TheaterName,
    s.BasePrice,
    th.TotalCapacity,
    s.CurrentOccupancy,
    ROUND((s.CurrentOccupancy::NUMERIC / th.TotalCapacity) * 100, 1)   AS CurrentFillPct,
    df.PredictedOccupancy,
    df.PredictedRevenue,
    df.RecommendationLevel,
    em.TMDB_Rating,
    em.TMDB_Popularity,
    em.TrendingStatus,
    -- rank each showtime by predicted revenue within its date
    RANK() OVER (
        PARTITION BY s.Date
        ORDER BY df.PredictedRevenue DESC NULLS LAST
    ) AS RevenueRankOnDate,
    -- running total of predicted revenue per movie over time
    SUM(df.PredictedRevenue) OVER (
        PARTITION BY m.MovieID
        ORDER BY s.Date, s.StartTime
        ROWS UNBOUNDED PRECEDING
    ) AS CumulativePredictedRevenue
FROM  Demand_Forecasts      df
JOIN  Showtimes              s  ON df.ShowtimeID = s.ShowtimeID
JOIN  Movies                 m  ON s.MovieID     = m.MovieID
JOIN  Theaters               th ON s.TheaterID   = th.TheaterID
LEFT JOIN External_Metadata  em ON m.MovieID     = em.MovieID
WITH NO DATA;


-- Top movies by revenue over the last 30 days, ranked within their genre
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_movie_performance AS
SELECT
    m.MovieID,
    m.Title,
    m.Genre,
    COUNT(b.BookingID)        AS TotalBookings,
    SUM(b.FinalPrice)         AS TotalRevenue,
    AVG(b.FinalPrice)         AS AvgTicketPrice,
    COUNT(DISTINCT b.UserID)  AS UniqueCustomers,
    -- rank by revenue within each genre
    RANK() OVER (
        PARTITION BY m.Genre
        ORDER BY SUM(b.FinalPrice) DESC NULLS LAST
    ) AS RevenueRankInGenre,
    -- each movie's share of total revenue
    ROUND(
        SUM(b.FinalPrice) / NULLIF(SUM(SUM(b.FinalPrice)) OVER (), 0) * 100, 2
    ) AS RevenueSharePct
FROM  Movies    m
JOIN  Showtimes s ON m.MovieID    = s.MovieID
JOIN  Bookings  b ON s.ShowtimeID = b.ShowtimeID
WHERE b.Status     = 'confirmed'
  AND b.BookingTime >= NOW() - INTERVAL '30 days'
GROUP BY m.MovieID, m.Title, m.Genre
WITH NO DATA;


-- -------------------------------------------------------------------------
-- 6. ROLE GUARD HELPER
-- Call PERFORM assert_role(user_id, 'admin') at the top of any
-- sensitive query to enforce access control.
-- -------------------------------------------------------------------------

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
        RAISE EXCEPTION 'Access denied: requires "%" but user has "%".',
            p_required_role, v_role;
    END IF;
END;
$$;



