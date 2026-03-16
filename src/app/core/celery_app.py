from celery import Celery
from src.app.core.config import load_config

settings = load_config()

celery_app = Celery(
    "movie_bot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.app.services.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tashkent",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max for transcoding
)

def get_worker_status():
    """
    Faol workerlar ro'yxatini qaytaradi.
    """
    try:
        inspect = celery_app.control.inspect()
        nodes = inspect.active()
        return nodes
    except Exception:
        return None

def is_worker_online():
    """
    Kamida bitta worker onlayn ekanligini tekshiradi.
    """
    status = get_worker_status()
    return status is not None and len(status) > 0
