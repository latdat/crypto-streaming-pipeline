CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE TABLE IF NOT EXISTS crypto_prices (
    time        TIMESTAMPTZ     NOT NULL,
    symbol      TEXT            NOT NULL,
    price       NUMERIC(18, 8)  NOT NULL,
    quantity    NUMERIC(18, 8)  NOT NULL,
    trade_id    BIGINT          NOT NULL,
    is_buyer_maker BOOLEAN      NOT NULL
);
SELECT create_hypertable(
    'crypto_prices',
    by_range('time', INTERVAL '1 day')
);
CREATE INDEX idx_symbol_time ON crypto_prices (symbol, time DESC);

CREATE MATERIALIZED VIEW crypto_prices_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time)  AS bucket,
    symbol,
    FIRST(price, time)              AS open,
    MAX(price)                      AS high,
    MIN(price)                      AS low,
    LAST(price, time)               AS close,
    SUM(quantity)                   AS volume,
    COUNT(*)                        AS trade_count
FROM crypto_prices
GROUP BY bucket, symbol
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'crypto_prices_5m',
    start_offset => INTERVAL '1 hour',
    end_offset   => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute'
);