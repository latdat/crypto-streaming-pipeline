import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import websockets
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PRODUCER] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Cấu hình ────────────────────────────────────────────────
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
TOPIC           = os.getenv("KAFKA_TOPIC", "crypto-prices")
SYMBOLS         = ["btcusdt", "ethusdt", "bnbusdt", "solusdt"]

BINANCE_WS = (
    "wss://stream.binance.com:9443/stream?streams="
    + "/".join(f"{s}@trade" for s in SYMBOLS)
)

# ── Kafka Producer ───────────────────────────────────────────
producer = Producer({
    "bootstrap.servers": KAFKA_BOOTSTRAP,
    "client.id":         "binance-producer",
    "acks":              "all",
    "retries":           5,
    "retry.backoff.ms":  500,
})

def delivery_report(err, msg):
    if err:
        log.error("Delivery failed | topic=%s err=%s", msg.topic(), err)

# ── Main loop ────────────────────────────────────────────────
async def stream():
    log.info("Connecting to Binance WebSocket...")
    log.info("Symbols: %s", SYMBOLS)
    log.info("Kafka:   %s → topic: %s", KAFKA_BOOTSTRAP, TOPIC)

    async for ws in websockets.connect(BINANCE_WS, ping_interval=20):
        try:
            log.info("WebSocket connected ✓")
            async for raw in ws:
                data = json.loads(raw)
                trade = data.get("data", {})

                if trade.get("e") != "trade":
                    continue

                message = {
                    "time":           datetime.fromtimestamp(
                                          trade["T"] / 1000,
                                          tz=timezone.utc
                                      ).isoformat(),
                    "symbol":         trade["s"],     # BTCUSDT
                    "price":          trade["p"],      # string giữ precision
                    "quantity":       trade["q"],
                    "trade_id":       trade["t"],
                    "is_buyer_maker": trade["m"],
                }

                producer.produce(
                    topic=TOPIC,
                    key=message["symbol"],
                    value=json.dumps(message),
                    callback=delivery_report,
                )
                producer.poll(0)

                log.info(
                    "%-10s price=%-14s qty=%s",
                    message["symbol"],
                    message["price"],
                    message["quantity"],
                )

        except websockets.ConnectionClosed:
            log.warning("WebSocket closed — reconnecting in 3s...")
            await asyncio.sleep(3)

        except Exception as e:
            log.error("Unexpected error: %s — reconnecting in 5s...", e)
            await asyncio.sleep(5)

        finally:
            producer.flush()

if __name__ == "__main__":
    asyncio.run(stream())