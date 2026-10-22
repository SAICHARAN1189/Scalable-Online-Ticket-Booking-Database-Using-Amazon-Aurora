-- ============================================================
-- Seed data — realistic sample events and a demo customer
-- ============================================================

-- Demo customer
INSERT INTO customers (full_name, email, phone)
VALUES ('Sai Charan', 'saicharan@example.com', '+91-9876543210')
ON CONFLICT (email) DO NOTHING;

-- Sample events (varied categories, dates, prices)
INSERT INTO events (title, description, venue, event_date, category, image_url, total_tickets, available_tickets, price)
VALUES
(
    'Arijit Singh Live in Concert',
    'Experience the magic of Arijit Singh performing his greatest hits live. An unforgettable evening of soulful music under the stars.',
    'Jawaharlal Nehru Stadium, Delhi',
    '2026-12-15 19:00:00',
    'Music',
    NULL,
    5000,
    4850,
    2500.00
),
(
    'IPL 2027 — Mumbai Indians vs Chennai Super Kings',
    'The biggest rivalry in IPL returns! Watch MI take on CSK in this blockbuster clash at the Wankhede.',
    'Wankhede Stadium, Mumbai',
    '2027-03-28 19:30:00',
    'Sports',
    NULL,
    33000,
    32500,
    1500.00
),
(
    'Stand-Up Comedy Night with Zakir Khan',
    'Get ready for an evening full of laughter with India''s favorite comedian. Zakir Khan brings his new show to Bangalore.',
    'Chowdiah Memorial Hall, Bangalore',
    '2026-11-20 20:00:00',
    'Comedy',
    NULL,
    800,
    780,
    1200.00
),
(
    'Diljit Dosanjh — Born to Shine Tour',
    'The ultimate Punjabi music extravaganza! Diljit Dosanjh brings his electrifying energy to Hyderabad for one night only.',
    'GMR Arena, Hyderabad',
    '2027-01-10 18:30:00',
    'Music',
    NULL,
    10000,
    9800,
    3000.00
),
(
    'Comic Con India 2027',
    'India''s biggest pop culture convention is back! Meet your favorite comic artists, cosplay, gaming tournaments and exclusive merchandise.',
    'NESCO Centre, Mumbai',
    '2027-02-14 10:00:00',
    'Exhibition',
    NULL,
    15000,
    14500,
    800.00
),
(
    'Bangalore Literature Festival',
    'A celebration of words featuring acclaimed authors, panel discussions, book launches and interactive workshops.',
    'The Lalit Ashok, Bangalore',
    '2026-12-05 09:00:00',
    'Conference',
    NULL,
    2000,
    1950,
    500.00
),
(
    'Sunburn Festival Goa 2027',
    'Asia''s premier electronic dance music festival returns to Goa with international DJs, stunning stages and three days of non-stop music.',
    'Vagator Beach, Goa',
    '2027-01-28 16:00:00',
    'Music',
    NULL,
    20000,
    19500,
    4500.00
),
(
    'India vs Australia — 1st Test',
    'The Border-Gavaskar Trophy continues! Watch India take on Australia in this gripping Test match at the iconic M.A. Chidambaram Stadium.',
    'M.A. Chidambaram Stadium, Chennai',
    '2027-02-20 09:30:00',
    'Sports',
    NULL,
    40000,
    39000,
    1000.00
),
(
    'TEDx Chennai 2027',
    'Ideas worth spreading — hear from innovators, artists, scientists and changemakers reshaping India and the world.',
    'IIT Madras, Chennai',
    '2027-03-15 09:00:00',
    'Conference',
    NULL,
    500,
    480,
    1500.00
),
(
    'Coldplay — Music of the Spheres World Tour',
    'Coldplay returns to India! Experience the spectacular Music of the Spheres World Tour with dazzling visuals and iconic hits.',
    'DY Patil Stadium, Navi Mumbai',
    '2027-04-05 18:00:00',
    'Music',
    NULL,
    50000,
    48000,
    6000.00
);
