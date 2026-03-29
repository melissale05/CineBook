-- =============================================================================
-- CineBook Seed Data  (Milestone 1 - synthetic data for testing)
-- Run AFTER schema.sql
-- =============================================================================

-- =============================================================================
-- USERS
-- Passwords are bcrypt hashes of "password123" — replace before production.
-- =============================================================================
INSERT INTO Users (Name, Email, Password, Role, FavoriteGenre, LoyaltyPoints) VALUES
  ('Admin User',      'admin@cinebook.com',   '$2b$12$placeholder_admin_hash',   'admin',    NULL,      0),
  ('Alice Johnson',   'alice@example.com',    '$2b$12$placeholder_alice_hash',   'customer', 'Action',  120),
  ('Bob Smith',       'bob@example.com',      '$2b$12$placeholder_bob_hash',     'customer', 'Horror',   85),
  ('Carol Williams',  'carol@example.com',    '$2b$12$placeholder_carol_hash',   'customer', 'Romance',  50),
  ('David Brown',     'david@example.com',    '$2b$12$placeholder_david_hash',   'customer', 'Sci-Fi',  200),
  ('Eva Martinez',    'eva@example.com',      '$2b$12$placeholder_eva_hash',     'customer', 'Comedy',   15),
  ('Frank Davis',     'frank@example.com',    '$2b$12$placeholder_frank_hash',   'customer', 'Drama',    90),
  ('Grace Wilson',    'grace@example.com',    '$2b$12$placeholder_grace_hash',   'customer', 'Action',  310),
  ('Henry Taylor',    'henry@example.com',    '$2b$12$placeholder_henry_hash',   'customer', 'Horror',   45),
  ('Isabel Anderson', 'isabel@example.com',   '$2b$12$placeholder_isabel_hash',  'customer', 'Sci-Fi',  175);

-- =============================================================================
-- THEATERS
-- =============================================================================
INSERT INTO Theaters (Name, Location, TotalCapacity, ScreenType) VALUES
  ('Hall A',        'Main Building - Floor 1', 150, 'Standard'),
  ('Hall B',        'Main Building - Floor 1', 120, 'Standard'),
  ('IMAX Screen',   'Main Building - Floor 2', 200, 'IMAX'),
  ('Dolby Atmos',   'East Wing - Floor 1',     100, 'Dolby'),
  ('Hall C',        'East Wing - Floor 2',      80, 'Standard');

-- =============================================================================
-- MOVIES
-- TMDB_IDs below are real TMDB movie IDs; metadata will be filled by fetch_tmdb.py
-- =============================================================================
INSERT INTO Movies (Title, Genre, Duration, ReleaseDate, TMDB_ID, Description, PosterURL) VALUES
  ('Dune: Part Two',        'Sci-Fi',  166, '2024-03-01',  693134,
   'Paul Atreides unites with the Fremen to seek revenge against the conspirators who destroyed his family.',
   'https://image.tmdb.org/t/p/w500/8b8R8l88Qje9dn9OE8PY05Nxl1X.jpg'),

  ('Godzilla x Kong: The New Empire', 'Action', 115, '2024-03-29', 823464,
   'Two ancient titans, Godzilla and Kong, clash in an epic battle as humans unravel their intertwined origins.',
   'https://image.tmdb.org/t/p/w500/z1p34vh7dEOnLDmyCrlUVLuoDzd.jpg'),

  ('Civil War',              'Drama',   109, '2024-04-12',  1087822,
   'A journey across a dystopian future America, following a team of journalists covering the outbreak of a civil war.',
   'https://image.tmdb.org/t/p/w500/sh7Rg8Er3tFcN9BpKIPOMvALgZd.jpg'),

  ('The Fall Guy',           'Action',  126, '2024-05-03',  746036,
   'A stuntman is drawn back into service when the star of a major film goes missing.',
   'https://image.tmdb.org/t/p/w500/tSz1qsmSJon0rqjHBxXZmrotuse.jpg'),

  ('A Quiet Place: Day One', 'Horror',   99, '2024-06-28',  762441,
   'A woman named Sam finds herself caught in the chaos of the invasion.',
   'https://image.tmdb.org/t/p/w500/yrpPYKijwdMHyTGIOd1iK1h0Ur8.jpg'),

  ('Inside Out 2',           'Animation', 100, '2024-06-14', 1022789,
   'Riley enters high school and her old emotions are joined by new ones.',
   'https://image.tmdb.org/t/p/w500/vpnVM9B6NMmQpWeZvzLvDESb2QY.jpg'),

  ('Alien: Romulus',         'Sci-Fi',  119, '2024-08-16',  945961,
   'A group of young people on a distant world discover a terrifying extraterrestrial life form.',
   'https://image.tmdb.org/t/p/w500/b33nnKl1GSFbao4l3fZDDqsMx0F.jpg'),

  ('Deadpool & Wolverine',   'Action',  127, '2024-07-26',  533535,
   'Deadpool is recruited by the Time Variance Authority and allies with Wolverine.',
   'https://image.tmdb.org/t/p/w500/8cdWjvZQUExUUTzyp4t6EDMubfO.jpg'),

  ('Longlegs',               'Horror',   101, '2024-07-12', 1100535,
   'An FBI agent is drawn deeper into a disturbing case involving a serial killer who leaves cryptic messages.',
   'https://image.tmdb.org/t/p/w500/oAbHtSJJvDYHgkfSRHHqJAN9FCG.jpg'),

  ('Twisters',               'Action',  122, '2024-07-19',  718821,
   'A former storm chaser returns to the field to test a daring new storm intercept technique.',
   'https://image.tmdb.org/t/p/w500/pjnD08FlMAIXsfOLKQbvmO0f0MD.jpg');

-- =============================================================================
-- SHOWTIMES
-- Spread across the next two weeks; variety of dates/times for testing
-- =============================================================================
INSERT INTO Showtimes (MovieID, TheaterID, StartTime, Date, BasePrice, CurrentOccupancy) VALUES
  -- Dune: Part Two (MovieID=1) in IMAX (TheaterID=3) — high demand scenario
  (1, 3, '10:00', CURRENT_DATE + 1,  18.99, 170),
  (1, 3, '14:00', CURRENT_DATE + 1,  18.99, 195),
  (1, 3, '18:30', CURRENT_DATE + 2,  18.99,  40),
  -- Godzilla x Kong (MovieID=2) in Hall A (TheaterID=1)
  (2, 1, '11:00', CURRENT_DATE + 1,  13.99,  30),
  (2, 1, '15:00', CURRENT_DATE + 2,  13.99,  80),
  (2, 1, '19:30', CURRENT_DATE + 3,  13.99, 140),
  -- Civil War (MovieID=3) in Hall B (TheaterID=2)
  (3, 2, '13:00', CURRENT_DATE + 2,  12.99,  10),
  (3, 2, '17:00', CURRENT_DATE + 4,  12.99,  55),
  -- The Fall Guy (MovieID=4) in Dolby Atmos (TheaterID=4)
  (4, 4, '12:00', CURRENT_DATE + 1,  15.99,  25),
  (4, 4, '16:00', CURRENT_DATE + 3,  15.99,  95),
  -- A Quiet Place: Day One (MovieID=5) in Hall A
  (5, 1, '20:00', CURRENT_DATE + 2,  13.99,  60),
  (5, 1, '22:00', CURRENT_DATE + 5,  11.99,   5),  -- late show — low demand
  -- Inside Out 2 (MovieID=6) in Hall C (TheaterID=5) — family-friendly matinee
  (6, 5, '10:00', CURRENT_DATE + 1,  10.99,  70),
  (6, 5, '13:00', CURRENT_DATE + 2,  10.99,  78),
  -- Alien: Romulus (MovieID=7) in Hall B
  (7, 2, '21:00', CURRENT_DATE + 3,  13.99,  20),
  (7, 2, '23:00', CURRENT_DATE + 4,  11.99,   8),
  -- Deadpool & Wolverine (MovieID=8) in IMAX — very high demand
  (8, 3, '12:00', CURRENT_DATE + 4,  18.99, 198),
  (8, 3, '17:00', CURRENT_DATE + 5,  18.99, 200),
  (8, 3, '21:30', CURRENT_DATE + 6,  18.99, 185),
  -- Longlegs (MovieID=9) in Hall C
  (9, 5, '20:30', CURRENT_DATE + 3,  12.99,  15),
  -- Twisters (MovieID=10) in Hall A
  (10, 1, '14:00', CURRENT_DATE + 5,  13.99,  45),
  (10, 1, '18:00', CURRENT_DATE + 6,  13.99,  90);

-- =============================================================================
-- BOOKINGS  (synthetic; mirrors CurrentOccupancy counts set above)
-- We only insert a sample — the full set would be generated programmatically.
-- =============================================================================

-- Alice (UserID=2) booked Dune: Part Two showtime 1 (ShowtimeID=1, seat A12)
INSERT INTO Bookings (UserID, ShowtimeID, SeatNumber, FinalPrice, Status) VALUES
  (2,  1,  'A12', 18.99, 'confirmed'),
  (3,  1,  'B7',  18.99, 'confirmed'),
  (4,  5,  'C3',  13.99, 'confirmed'),
  (5,  17, 'D1',  18.99, 'confirmed'),
  (6,  13, 'A1',  10.99, 'confirmed'),
  (7,  8,  'F6',  12.99, 'confirmed'),
  (8,  17, 'E10', 18.99, 'confirmed'),
  (9,  11, 'G4',  13.99, 'confirmed'),
  (10, 3,  'B2',  18.99, 'confirmed'),
  (2,  20, 'A5',  12.99, 'confirmed'),
  -- Cancelled booking to verify trigger
  (3,  13, 'A2',  10.99, 'cancelled');

-- =============================================================================
-- DEMAND FORECASTS  (initial seeded forecasts; engine will overwrite these)
-- =============================================================================
INSERT INTO Demand_Forecasts (ShowtimeID, PredictedOccupancy, PredictedRevenue, RecommendationLevel) VALUES
  (1,  95.00,  1804.05, 'high_demand'),
  (2,  99.00,  1879.01, 'add_screening'),
  (3,  25.00,   474.75, 'adjust_price'),
  (4,  40.00,   839.40, 'normal'),
  (5,  65.00,  1119.20, 'normal'),
  (6,  90.00,  1960.14, 'high_demand'),
  (7,  15.00,   233.82, 'adjust_price'),
  (17, 99.00,  3762.02, 'add_screening'),
  (18,100.00,  3798.00, 'add_screening'),
  (12,  8.00,    95.92, 'adjust_price');
