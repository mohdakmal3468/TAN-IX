-- ==============================================================================
-- TAN-IX: Analytical SQL Queries for Google Cloud BigQuery
-- Dataset: leather_logistics
-- Tables : transit_logs, order_history
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- QUERY 1: Average Transit Delay and On-Time Reliability per Route Lane
-- Identifies expressway bottlenecks, average transit hours, and delay frequency
-- ------------------------------------------------------------------------------
SELECT
    route,
    origin,
    destination,
    COUNT(*) AS total_shipments,
    ROUND(AVG(planned_hours), 2) AS avg_planned_hours,
    ROUND(AVG(actual_hours), 2) AS avg_actual_hours,
    ROUND(AVG(delay_hours), 2) AS avg_delay_hours,
    ROUND(COUNT(CASE WHEN delay_hours > 0.5 THEN 1 END) * 100.0 / COUNT(*), 1) AS delay_percentage,
    ROUND(COUNT(CASE WHEN delay_hours <= 0.5 THEN 1 END) * 100.0 / COUNT(*), 1) AS on_time_percentage
FROM
    `leather_logistics.transit_logs`
GROUP BY
    route,
    origin,
    destination
ORDER BY
    avg_delay_hours DESC;


-- ------------------------------------------------------------------------------
-- QUERY 2: Monthly Stockout and Shortage Incidents per District
-- Analyzes unfulfilled order demand across Kanpur, Unnao, Agra, and Noida
-- ------------------------------------------------------------------------------
SELECT
    SUBSTR(date, 1, 7) AS order_month,
    district,
    product,
    COUNT(*) AS total_orders,
    COUNT(CASE WHEN is_stockout = 'TRUE' OR is_stockout = 1 THEN 1 END) AS stockout_incidents,
    ROUND(COUNT(CASE WHEN is_stockout = 'TRUE' OR is_stockout = 1 THEN 1 END) * 100.0 / COUNT(*), 1) AS stockout_rate_pct,
    SUM(requested_quantity - fulfilled_quantity) AS total_unfulfilled_units
FROM
    `leather_logistics.order_history`
GROUP BY
    order_month,
    district,
    product
HAVING
    stockout_incidents > 0
ORDER BY
    order_month DESC,
    stockout_incidents DESC;


-- ------------------------------------------------------------------------------
-- QUERY 3: Freight Spend, Efficiency, and Cost per Carrier
-- Compares carrier performance: cost per km, total spend, and reliability
-- ------------------------------------------------------------------------------
SELECT
    carrier,
    COUNT(*) AS total_trips,
    SUM(quantity) AS total_units_transported,
    SUM(cost_inr) AS total_spend_inr,
    ROUND(AVG(cost_inr), 2) AS avg_cost_per_trip_inr,
    ROUND(AVG(CAST(cost_inr AS FLOAT) / distance_km), 2) AS avg_cost_per_km_inr,
    ROUND(AVG(delay_hours), 2) AS avg_delay_hours
FROM
    `leather_logistics.transit_logs`
GROUP BY
    carrier
ORDER BY
    total_spend_inr DESC;
