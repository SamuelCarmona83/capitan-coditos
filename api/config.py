import os


class Config:
    MONGO_URL: str = os.getenv("MONGO_URL", "mongodb://mongo:27017")
    MONGO_DB: str = os.getenv("MONGO_DB", "capitancoditos")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    RIOT_API_KEY: str = os.getenv("RIOT_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Celery
    CELERY_BROKER_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    # Prefetch worker
    PREFETCH_INTERVAL_MINUTES: int = int(os.getenv("PREFETCH_INTERVAL_MINUTES", "30"))
    PREFETCH_MATCH_COUNT: int = int(os.getenv("PREFETCH_MATCH_COUNT", "20"))

    # CORS – tighten in production via env var
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")
