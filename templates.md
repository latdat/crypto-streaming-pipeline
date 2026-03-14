# Kafka Topic
## Tạo kafka topic template
```
docker exec kafka kafka-topics.sh \
 --bootstrap-server localhost:9092 \
 --create \
 --topic <topic_name> \
 --partitions <n> \
 --replication-factor <n>
```
## Check topic
```
docker exec kafka kafka-topics.sh \
 --bootstrap-server localhost:9092 \
 --describe \
 --topic <topic_name>
```

# Tạo schema Timescale DB
Mở file db/init.sql và paste nội dung:
```
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Bảng chính lưu raw tick data
CREATE TABLE IF NOT EXISTS crypto_prices (
    time        TIMESTAMPTZ     NOT NULL,
    symbol      TEXT            NOT NULL,
    price       NUMERIC(18, 8)  NOT NULL,
    quantity    NUMERIC(18, 8)  NOT NULL,
    trade_id    BIGINT          NOT NULL,
    is_buyer_maker BOOLEAN      NOT NULL
);

-- Chuyển thành hypertable (TimescaleDB magic ✨)
SELECT create_hypertable(
    'crypto_prices',
    by_range('time', INTERVAL '1 day')
);

-- Index để query nhanh theo symbol + time
CREATE INDEX idx_symbol_time ON crypto_prices (symbol, time DESC);

-- Continuous Aggregate: OHLCV mỗi 5 phút
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

-- Auto-refresh continuous aggregate mỗi 1 phút
SELECT add_continuous_aggregate_policy(
    'crypto_prices_5m',
    start_offset => INTERVAL '1 hour',
    end_offset   => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute'
);
```
# Health check query (chạy mỗi sáng)
```
sql-- Bao nhiêu trade trong 1 giờ qua?
SELECT symbol, COUNT(*) as trades_last_hour
FROM crypto_prices
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY symbol ORDER BY symbol;

-- Disk usage
SELECT hypertable_name,
       pg_size_pretty(hypertable_size('crypto_prices')) as total_size;
```