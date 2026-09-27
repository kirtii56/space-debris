-- Space Debris Tracker schema.
-- Written in portable SQL so the same file runs on SQLite (local) and PostgreSQL (Docker).

-- One row per tracked object, refreshed on every ingest.
CREATE TABLE IF NOT EXISTS objects (
    norad_id            INTEGER PRIMARY KEY,
    name                TEXT NOT NULL,
    object_type         TEXT NOT NULL,          -- PAYLOAD / DEBRIS / ROCKET BODY
    intl_designator     TEXT,
    launch_id           TEXT,                   -- e.g. 99025 = the launch this object came from
    source_group        TEXT NOT NULL,          -- CelesTrak group it was downloaded from
    epoch               TIMESTAMP NOT NULL,     -- when this TLE was measured
    inclination_deg     DOUBLE PRECISION,
    raan_deg            DOUBLE PRECISION,
    eccentricity        DOUBLE PRECISION,
    arg_perigee_deg     DOUBLE PRECISION,
    mean_anomaly_deg    DOUBLE PRECISION,
    mean_motion_rev_day DOUBLE PRECISION,
    bstar               DOUBLE PRECISION,
    period_min          DOUBLE PRECISION,
    semi_major_axis_km  DOUBLE PRECISION,
    perigee_km          DOUBLE PRECISION,
    apogee_km           DOUBLE PRECISION,
    orbit_class         TEXT,                   -- LEO / MEO / GEO / HEO / OTHER
    altitude_band_km    INTEGER,                -- perigee rounded down to 100 km
    tle_line1           TEXT NOT NULL,
    tle_line2           TEXT NOT NULL,
    ingested_at         TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_objects_type ON objects (object_type);
CREATE INDEX IF NOT EXISTS idx_objects_orbit ON objects (orbit_class);
CREATE INDEX IF NOT EXISTS idx_objects_group ON objects (source_group);
CREATE INDEX IF NOT EXISTS idx_objects_perigee ON objects (perigee_km);

-- Close approaches found by the screening step.
CREATE TABLE IF NOT EXISTS conjunctions (
    primary_norad           INTEGER NOT NULL,
    secondary_norad         INTEGER NOT NULL,
    tca                     TIMESTAMP NOT NULL,  -- time of closest approach (UTC)
    miss_distance_km        DOUBLE PRECISION NOT NULL,
    relative_velocity_km_s  DOUBLE PRECISION NOT NULL,
    collision_probability   DOUBLE PRECISION,
    screened_at             TIMESTAMP NOT NULL,
    PRIMARY KEY (primary_norad, secondary_norad, tca)
);

-- Output of the DBSCAN breakup-clustering model.
CREATE TABLE IF NOT EXISTS debris_clusters (
    norad_id    INTEGER PRIMARY KEY,
    cluster_id  INTEGER NOT NULL,               -- -1 = noise (no cluster)
    run_at      TIMESTAMP NOT NULL
);

-- Analytics views used by the API and dashboard.
DROP VIEW IF EXISTS v_summary_by_type;
CREATE VIEW v_summary_by_type AS
SELECT object_type,
       COUNT(*)                AS object_count,
       AVG(perigee_km)         AS avg_perigee_km,
       AVG(inclination_deg)    AS avg_inclination_deg
FROM objects
GROUP BY object_type;

DROP VIEW IF EXISTS v_summary_by_orbit;
CREATE VIEW v_summary_by_orbit AS
SELECT orbit_class,
       object_type,
       COUNT(*) AS object_count
FROM objects
GROUP BY orbit_class, object_type;

DROP VIEW IF EXISTS v_altitude_density;
CREATE VIEW v_altitude_density AS
SELECT altitude_band_km,
       SUM(CASE WHEN object_type = 'DEBRIS' THEN 1 ELSE 0 END)  AS debris_count,
       SUM(CASE WHEN object_type = 'PAYLOAD' THEN 1 ELSE 0 END) AS payload_count,
       COUNT(*)                                                  AS total_count
FROM objects
WHERE orbit_class = 'LEO'
GROUP BY altitude_band_km;

DROP VIEW IF EXISTS v_breakup_events;
CREATE VIEW v_breakup_events AS
SELECT source_group,
       COUNT(*)                AS fragments_tracked,
       MIN(perigee_km)         AS lowest_perigee_km,
       MAX(apogee_km)          AS highest_apogee_km,
       AVG(inclination_deg)    AS avg_inclination_deg
FROM objects
WHERE source_group LIKE '%-debris' AND object_type = 'DEBRIS'
GROUP BY source_group;

DROP VIEW IF EXISTS v_conjunctions_detail;
CREATE VIEW v_conjunctions_detail AS
SELECT c.primary_norad,
       p.name   AS primary_name,
       c.secondary_norad,
       s.name   AS secondary_name,
       s.object_type AS secondary_type,
       c.tca,
       c.miss_distance_km,
       c.relative_velocity_km_s,
       c.collision_probability,
       c.screened_at
FROM conjunctions c
JOIN objects p ON p.norad_id = c.primary_norad
JOIN objects s ON s.norad_id = c.secondary_norad;
