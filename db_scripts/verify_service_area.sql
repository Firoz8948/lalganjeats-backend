-- Verify customer visibility against each tenant's locked centre + max active zone.
--
-- Usage (set the customer coordinates you want to test):
--   psql "$DATABASE_URL" \
--     -v cust_lat=25.93 -v cust_lng=81.70 \
--     -f db_scripts/verify_service_area.sql

\if :{?cust_lat}
\else
  \set cust_lat 25.93
\endif
\if :{?cust_lng}
\else
  \set cust_lng 81.70
\endif

WITH customer AS (
    SELECT :cust_lat::float8 AS lat, :cust_lng::float8 AS lng
),
zone_limits AS (
    SELECT tenant_id, MAX(COALESCE(final_km, radius_km)) AS max_radius_km, COUNT(*) AS active_zones
    FROM delivery_zones
    WHERE is_active = true
    GROUP BY tenant_id
)
SELECT
    t.id                AS tenant_id,
    t.name              AS tenant,
    t.center_latitude   AS center_lat,
    t.center_longitude  AS center_lng,
    z.active_zones,
    z.max_radius_km,
    ROUND((
        2 * 6371.0 * asin(sqrt(
            power(sin(radians(t.center_latitude::float8 - c.lat) / 2), 2)
            + cos(radians(c.lat)) * cos(radians(t.center_latitude::float8))
            * power(sin(radians(t.center_longitude::float8 - c.lng) / 2), 2)
        ))
    )::numeric, 2)      AS distance_km,
    CASE
        WHEN z.max_radius_km IS NULL THEN 'NO ACTIVE ZONES -> hidden'
        WHEN (
            2 * 6371.0 * asin(sqrt(
                power(sin(radians(t.center_latitude::float8 - c.lat) / 2), 2)
                + cos(radians(c.lat)) * cos(radians(t.center_latitude::float8))
                * power(sin(radians(t.center_longitude::float8 - c.lng) / 2), 2)
            ))
        ) < z.max_radius_km THEN 'IN RANGE -> visible'
        ELSE 'OUT OF RANGE -> hidden'
    END                 AS verdict,
    (SELECT COUNT(*) FROM restaurants r
      WHERE r.tenant_id = t.id AND r.is_active AND r.is_approved) AS live_restaurants
FROM tenants t
CROSS JOIN customer c
LEFT JOIN zone_limits z ON z.tenant_id = t.id
ORDER BY distance_km;
