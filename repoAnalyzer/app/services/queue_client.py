from typing import Any, Optional
import aio_pika
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("queue_client")

_queue_connection: Optional[aio_pika.RobustConnection] = None
_queue_channel: Optional[aio_pika.RobustChannel] = None


async def get_queue_connection() -> Optional[aio_pika.RobustConnection]:
    """Get or initialize the AMQP / RabbitMQ connection."""
    global _queue_connection, _queue_channel
    if _queue_connection is None:
        try:
            logger.info("Connecting to message broker", url=settings.RABBITMQ_URL)
            _queue_connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            _queue_channel = await _queue_connection.channel()
        except Exception as e:
            logger.warning("Message broker connection not available (will retry when needed)", error=str(e))
            return None
    return _queue_connection


async def publish_message(queue_name: str, message_body: dict[str, Any]) -> bool:
    """Publish a structured message to the message broker queue."""
    conn = await get_queue_connection()
    if conn is None or _queue_channel is None:
        logger.warning("Queue broker offline; skipping queue publish", queue=queue_name)
        return False

    import json
    await _queue_channel.declare_queue(queue_name, durable=True)
    await _queue_channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(message_body).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=queue_name,
    )
    logger.info("Message published to queue", queue=queue_name)
    return True


async def close_queue_connection() -> None:
    """Close the message queue connection."""
    global _queue_connection, _queue_channel
    if _queue_channel is not None:
        await _queue_channel.close()
        _queue_channel = None
    if _queue_connection is not None:
        await _queue_connection.close()
        _queue_connection = None
