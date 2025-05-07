from celery import Celery
import config

# Initialize Celery application
celery_app = Celery(
    'roboseg_tasks',
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    enable_utc=True,
    task_routes={
        'tasks.process_video_for_segmentation': {'queue': 'celery'},
    },
    imports=['tasks'],
)

# Empty autodiscover to avoid package import issues
celery_app.autodiscover_tasks([]) 