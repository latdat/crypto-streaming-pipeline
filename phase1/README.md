# Phase 1 — Real-time Pipeline & Reliability
### Binance API · Kafka · TimescaleDB · Prometheus · Grafana · Power BI

> **Mục tiêu | Goal:** Xây dựng streaming pipeline real-time hoàn chỉnh với cơ chế xử lý lỗi (Retry/DLQ), Manual Offset Commit và Monitoring/Alerting đầy đủ.
>
> Build a complete real-time streaming pipeline with error handling (Retry/DLQ), Manual Offset Commit, and full Monitoring/Alerting.

---

## 🏗️ Architecture | Kiến trúc

```
Binance WebSocket (4 symbols)
         │
         ▼
   Producer (Python)
   confluent-kafka · websockets
         │
         ▼
Apache Kafka 4.1.1 (KRaft mode)
   topic: crypto-prices (3 partitions)
         │
    ┌────┴────┐
    │  Error  │
    ▼         ▼
Consumer    DLQ topic
(Retry x3)  crypto-prices-dlq
    │
    ▼
TimescaleDB (PostgreSQL 16)
   Hypertable · OHLCV 5m Continuous Aggregate
    │
    ▼
Power BI (DirectQuery · 30s refresh)

── Monitoring ──────────────────────────
kminion (Kafka)  ──┐
postgres-exporter ─┼──► Prometheus ──► Grafana ──► Email Alert
───────────────────┘
```

---

## 📦 Services | Các services

| Service | Image | Port | Mô tả |
|---------|-------|------|-------|
| kafka | apache/kafka:4.1.1 | 9092 | Message broker (KRaft mode) |
| timescaledb | timescale/timescaledb:latest-pg16 | 5433 | Time-series database |
| producer | custom Python | — | Binance WebSocket → Kafka |
| consumer | custom Python | — | Kafka → TimescaleDB (Retry/DLQ) |
| kafka-ui | provectuslabs/kafka-ui | 8080 | Kafka management UI |
| kminion | redpandadata/kminion | 9308 | Kafka metrics exporter |
| postgres-exporter | prometheuscommunity/postgres-exporter | 9187 | DB metrics exporter |
| prometheus | prom/prometheus | 9090 | Metrics collection |
| grafana | grafana/grafana | 3000 | Dashboard & Alerting |

---

## ⚙️ Setup | Cài đặt

### 1. Prerequisites | Yêu cầu
```
Docker Desktop (Windows) — enable WSL2 backend
Python 3.12+
Power BI Desktop
```

### 2. Clone & Configure | Clone và cấu hình
```bash
git clone https://github.com/latdat/crypto-streaming-pipeline.git
cd crypto-streaming-pipeline/phase1
```

Tạo file `.env` (không commit lên GitHub):
```env
POSTGRES_DB=crypto_db
POSTGRES_USER=crypto_user
POSTGRES_PASSWORD=your_password
```

### 3. Start services | Khởi động
```bash
# Start all services
docker compose up -d

# Verify containers healthy
docker compose ps
```

### 4. Create Kafka topics | Tạo Kafka topics
```bash
# Main topic
docker exec kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create --topic crypto-prices \
  --partitions 3 --replication-factor 1

# Dead Letter Queue
docker exec kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create --topic crypto-prices-dlq \
  --partitions 3 --replication-factor 1
```

### 5. Verify data flow | Kiểm tra data
```bash
# Check consumer logs
docker logs consumer --tail 20 --follow

# Check DB
docker exec -it timescaledb psql -U crypto_user -d crypto_db \
  -c "SELECT symbol, COUNT(*), MAX(time) FROM crypto_prices GROUP BY symbol;"
```

---

## 🔒 Reliability Features | Tính năng độ tin cậy

### Retry + Dead Letter Queue
```
Insert fails → Retry attempt 1 (wait 2s)
            → Retry attempt 2 (wait 4s)
            → Retry attempt 3 (wait 8s)
            → Send to crypto-prices-dlq (no data loss)
```

### Manual Offset Commit
```python
# Offset chỉ được commit SAU KHI insert DB thành công
# Offset only committed AFTER successful DB insert
consumer.commit(asynchronous=False)  # called after conn.commit()
```

---

## 📊 Monitoring | Giám sát

### Access points | Các điểm truy cập
| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| Kafka UI | http://localhost:8080 | — |

### Grafana Dashboard Panels
| Panel | Metric | Normal Range |
|-------|--------|-------------|
| Consumer Lag | `kminion_kafka_consumer_group_topic_lag` | 4 – 36 |
| Partition Watermark | `kminion_kafka_topic_partition_high_water_mark` | Increasing |
| Broker Disk Usage | `kminion_kafka_broker_log_dir_size_total_bytes` | Steady growth |
| DB Inserts/sec | `rate(pg_stat_database_tup_inserted[1m])` | > 0 |

### Alert Rules
| Alert | Condition | Meaning |
|-------|-----------|---------|
| Consumer Lag High | lag > 100 | Consumer falling behind producer |
| Pipeline Stopped | watermark < 1 | No data from Binance |

---

## 🗄️ Database Schema | Schema database

```sql
-- Hypertable (partitioned by day)
CREATE TABLE crypto_prices (
    time           TIMESTAMPTZ     NOT NULL,
    symbol         TEXT            NOT NULL,
    price          NUMERIC(18, 8)  NOT NULL,
    quantity       NUMERIC(18, 8)  NOT NULL,
    trade_id       BIGINT          NOT NULL,
    is_buyer_maker BOOLEAN         NOT NULL
);

-- Continuous Aggregate: OHLCV 5-minute candles
CREATE MATERIALIZED VIEW crypto_prices_5m ...
-- Auto-refresh every 1 minute
```

---

## 📁 Structure | Cấu trúc thư mục

```
phase1/
├── docker-compose.yml
├── .env                    ← không commit (gitignored)
├── .gitignore
├── producer/
│   ├── producer.py         ← Binance WebSocket → Kafka
│   ├── requirements.txt
│   └── Dockerfile
├── consumer/
│   ├── consumer.py         ← Kafka → TimescaleDB (Retry/DLQ)
│   ├── requirements.txt
│   └── Dockerfile
├── db/
│   └── init.sql            ← Schema + Hypertable + OHLCV view
├── monitoring/
│   └── prometheus.yml      ← Scrape config
└── docs/
    ├── Phase1_Documentation.docx
    └── Phase2_Documentation.docx
```

---

## 🔧 Troubleshooting | Xử lý sự cố

| Issue | Solution |
|-------|----------|
| `kafka-exporter` no metrics | Use `redpandadata/kminion` — danielqsj/kafka-exporter không support Kafka 4.x KRaft |
| Prometheus target DOWN | kminion dùng port `:8080`, không phải `:9308` — kiểm tra `prometheus.yml` |
| Consumer không nhận data | `auto.offset.reset: latest` — chỉ nhận message mới sau khi start |
| DB auth failed | Đổi `pg_hba.conf` sang `md5` — psycopg2-binary trên Windows không support scram-sha-256 |
| Topics mất sau `down -v` | Tạo lại bằng kafka-topics.sh (xem bước 4 ở trên) |

---

## 📸 Screenshots | Ảnh minh họa

> *(Add screenshots here after capturing)*
> - [ ] Kafka UI — messages flowing
> - [ ] Grafana dashboard — 4 panels with live data
> - [ ] Alert email received
> - [ ] Power BI dashboard
> - [ ] TimescaleDB query result

---

## 📈 Performance | Hiệu năng

- **Throughput:** ~500 trades/second from Binance
- **Batch size:** 50 rows per flush, every 2 seconds (~1,000 rows/batch)
- **Consumer lag:** Stable at 4–36 messages
- **DB insert rate:** ~250 rows/second sustained
- **Retention:** 7 days rolling window with auto-compression

---

*← [Back to main README](../README.md)*