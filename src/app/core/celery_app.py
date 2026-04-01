from celery import Celery

from src.app.core.config import load_config

settings = load_config()

celery_app = Celery(
    "movie_bot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.app.services.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tashkent",
    enable_utc=True,
    task_track_started=True,
    # BUG FIX #1: task_time_limit 1 soat — katta filmlar uchun yetmaydi
    # 5 soatlik film = ~25-40 daqiqa, lekin upload ham qo'shilsa ko'proq
    task_time_limit=18000,  # 5 soat hard limit
    task_soft_time_limit=14400,  # 4 soat — graceful stop
    # BUG FIX #2: Redis connection yo'qolsa worker qayta ulansin
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_connection_timeout=30,
    # BUG FIX #3: worker o'lib qolsa task yo'qolmasin
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # BUG FIX #4: concurrency=2 bilan 2 ta task parallel ishlaydi
    # Lekin GTX 1050 Ti faqat 1 NVENC sessiya — bitta task ishlashi kerak
    # docker-compose da --concurrency=1 qilinishi kerak (yoki bu yerda)
    worker_concurrency=1,
    # Katta fayllar uchun result backend timeout
    result_expires=86400,  # 24 soat
    # Redis visibility_timeout: 6 soat (21600s)
    # Long tasklar uchun redelivery oldini olish
    broker_transport_options={
        "visibility_timeout": 21600,
    },
)


def get_worker_status():
    """Faol workerlar ro'yxatini qaytaradi."""
    try:
        inspect = celery_app.control.inspect(timeout=3)  # BUG FIX #5: timeout qo'shildi
        nodes = inspect.active()
        return nodes
    except Exception:
        return None


def is_worker_online() -> bool:
    """Kamida bitta worker onlayn ekanligini tekshiradi."""
    status = get_worker_status()
    return bool(status and len(status) > 0)
