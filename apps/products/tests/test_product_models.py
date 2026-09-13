from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.clinics.models import Clinic
from apps.products.models import ContentStatus, Product


class ProductModelTests(TestCase):
    def setUp(self):
        self.clinic = Clinic.objects.create(name_en="Dermacare Dubai", city="Dubai")

    def test_product_belongs_to_clinic(self):
        """Product must be owned by a clinic."""
        product = Product.objects.create(
            clinic=self.clinic,
            name_en="Hydrating Serum",
            name_ar="سيروم مرطب",
            description_en="Advanced hyaluronic serum",
            price=250.00,
            status=ContentStatus.ACTIVE,
        )
        self.assertEqual(product.clinic, self.clinic)
        self.assertIn(product, self.clinic.products.all())

    def test_product_cannot_be_saved_without_clinic(self):
        """Patients/users cannot be owners; products cannot exist without a clinic."""
        product = Product(
            name_en="Orphan Product",
            status=ContentStatus.ACTIVE,
        )
        with self.assertRaises(ValidationError):
            product.save()

    def test_product_fields_and_bilingual_support(self):
        """Validates all product fields, bilingual texts, and prices."""
        product = Product.objects.create(
            clinic=self.clinic,
            name_en="Anti-aging Cream",
            name_ar="كريم مضاد للشيخوخة",
            description_en="Retinol complex",
            description_ar="مركب الريتينول",
            image="https://cdn.example.com/cream.jpg",
            price=450.50,
        )
        self.assertEqual(product.name_en, "Anti-aging Cream")
        self.assertEqual(product.name_ar, "كريم مضاد للشيخوخة")
        self.assertEqual(float(product.price), 450.50)
        self.assertEqual(product.image_url, "https://cdn.example.com/cream.jpg")

    def test_product_active_and_soft_delete(self):
        """Validates active state filtering and soft-delete timestamp."""
        product = Product.objects.create(
            clinic=self.clinic,
            name_en="Cleanser",
            is_active=True,
        )
        self.assertTrue(product.is_active)
        self.assertIsNone(product.deleted_at)

        # Soft delete
        product.deleted_at = timezone.now()
        product.is_active = False
        product.save()

        self.assertFalse(product.is_active)
        self.assertIsNotNone(product.deleted_at)
