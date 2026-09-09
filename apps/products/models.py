import uuid
from django.db import models

class ContentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    REJECTED = "rejected", "Rejected"

class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_en = models.CharField(max_length=200)
    status = models.CharField(
        max_length=20, choices=ContentStatus.choices, default=ContentStatus.PENDING
    )

    class Meta:
        db_table = "products"
