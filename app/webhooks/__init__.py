# app/webhooks/__init__.py
from . import views
from .views import webhooks

__all__ = ["webhooks", "views"]