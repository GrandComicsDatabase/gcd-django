from django.apps import AppConfig


class ForumConfig(AppConfig):
    """The forum app, "Forum" in the admin, with AutoField ids like the site's DEFAULT_AUTO_FIELD."""
    default_auto_field = "django.db.models.AutoField"
    name = "apps.forum"
    verbose_name = "Forum"
