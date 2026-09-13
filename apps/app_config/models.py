from django.db import models


class PlatformSetting(models.Model):
    key = models.CharField(max_length=100, primary_key=True)
    value = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "platform_settings"
