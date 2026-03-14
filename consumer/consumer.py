import json
import logging
import os
import time
from datetime import timezone

import psycopg2
import psycopg2.extras
from confluent_kafka import Consumer, KafkaError
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CONSUMER] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Cấu hình ────────────────────────────────────────────────
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
TOPIC           = os.getenv("KAFKA_TOPIC", "crypto-prices")
GROUP_ID        = os.getenv("KAFKA_GROUP_ID", "crypto-consumer-group")

DB_HOST = os.getenv("DB_HOST", "timescaledb")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "crypto_db")
DB_USER = os.getenv("POSTGRES_USER", "crypto_user")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "cryptopass235371")

BATCH_SIZE     = int(os.getenv("BATCH_SIZE", "50"))
FLUSH_INTERVAL = float(os.getenv("FLUSH_INTERVAL", "2.0"))  # seconds

INSERT_SQL = """
    INSERT INTO crypto_prices
        (time, symbol, price, quantity, trade_id, is_buyer_maker)
    VALUES %s
    ON CONFLICT DO NOTHING
"""

# ── DB Connection ─────────────────────────────────────────────
def connect_db():
    while True:
        try:
            conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT,
                dbname=DB_NAME, user=DB_USER, password=DB_PASS
            )
            conn.autocommit = False
            log.info("TimescaleDB connected ✓")
            return conn
        except psycopg2.OperationalError as e:
            log.warning("DB not ready: %s — retry in 3s...", e)
            time.sleep(3)

# ── Kafka Consumer ────────────────────────────────────────────
def create_consumer():
    return Consumer({
        "bootstrap.servers":  KAFKA_BOOTSTRAP,
        "group.id":           GROUP_ID,
        "auto.offset.reset":  "latest",
        "enable.auto.commit": False,
    })

# ── Main loop ─────────────────────────────────────────────────
def main():
    log.info("Starting consumer...")
    log.info("Kafka: %s | Topic: %s | Group: %s", KAFKA_BOOTSTRAP, TOPIC, GROUP_ID)
    log.info("DB:    %s:%s/%s", DB_HOST, DB_PORT, DB_NAME)
    log.info("Batch: %d rows | Flush every: %.1fs", BATCH_SIZE, FLUSH_INTERVAL)

    conn = connect_db()
    cur  = conn.cursor()

    consumer = create_consumer()
    consumer.subscribe([TOPIC])
    log.info("Subscribed to topic: %s ✓", TOPIC)

    batch      = []
    last_flush = time.monotonic()
    total_rows = 0

    try:
        while True:
            msg = consumer.poll(timeout=0.5)

            if msg is None:
                pass
            elif msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    log.error("Kafka error: %s", msg.error())
            else:
                try:
                    trade = json.loads(msg.value().decode("utf-8"))
                    batch.append((
                        trade["time"],
                        trade["symbol"],
                        trade["price"],
                        trade["quantity"],
                        trade["trade_id"],
                        trade["is_buyer_maker"],
                    ))
                except (json.JSONDecodeError, KeyError) as e:
                    log.warning("Bad message: %s", e)

            # Flush khi đủ batch hoặc hết timeout
            now = time.monotonic()
            should_flush = (
                len(batch) >= BATCH_SIZE or
                (batch and now - last_flush >= FLUSH_INTERVAL)
            )

            if should_flush:
                try:
                    psycopg2.extras.execute_values(
                        cur, INSERT_SQL, batch, page_size=BATCH_SIZE
                    )
                    conn.commit()
                    consumer.commit(asynchronous=False)

                    total_rows += len(batch)
                    log.info(
                        "Flushed %3d rows | total=%d | last=%s @ %s",
                        len(batch),
                        total_rows,
                        batch[-1][1],   # symbol
                        batch[-1][0],   # time
                    )
                    batch.clear()
                    last_flush = now

                except psycopg2.Error as e:
                    log.error("DB insert error: %s — reconnecting...", e)
                    conn.rollback()
                    conn = connect_db()
                    cur  = conn.cursor()
                    batch.clear()

    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        consumer.close()
        cur.close()
        conn.close()
        log.info("Consumer stopped. Total rows inserted: %d", total_rows)

if __name__ == "__main__":
    main()