from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    """
    Wires the app's side effects at startup.

    Signal handlers and the pipeline thread are connected from ``ready()``
    rather than at module import, because importing models before the app
    registry is populated raises AppRegistryNotReady.
    """

    name = 'analytics'
    verbose_name = 'Visitor analytics'

    def ready(self) -> None:
        from . import signals  # noqa: F401  (registers the handlers)
        from .pipeline import start_scheduler

        start_scheduler()
