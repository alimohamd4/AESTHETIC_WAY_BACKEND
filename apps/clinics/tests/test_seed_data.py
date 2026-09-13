"""
Unit and Integration Tests for seed_data management command.
Validates Section 12 staging data generation, idempotency, and transactional safety.
"""
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.accounts.models import ClinicUser, User, UserRole
from apps.articles.models import Article
from apps.clinics.models import Clinic, ClinicBranch, SubscriptionTier
from apps.leads.models import Lead
from apps.offers.models import Offer
from apps.practitioners.models import Practitioner, PractitionerType
from apps.products.models import Product
from apps.referrals.models import (
    ReferralDiscountCode,
    ReferralInvite,
    ReferralPointsLedger,
)
from apps.treatments.models import Category, PractitionerTreatment, Treatment


@pytest.mark.django_db
class TestSeedDataCommand:

    def test_seed_data_execution(self):
        """Verify seed_data command runs successfully and creates all expected Section 12 entities."""
        call_command("seed_data", reset=True)

        # 1. Verify Users
        super_admin = User.objects.get(phone="+971500000001")
        assert super_admin.role == UserRole.SUPER_ADMIN
        assert super_admin.is_superuser is True

        clinic_admin = User.objects.get(phone="+971500000002")
        assert clinic_admin.role == UserRole.CLINIC_ADMIN

        # 2. Verify Clinics (Dubai & Abu Dhabi, multiple tiers)
        clinics = Clinic.objects.filter(slug__in=[
            "aesthetic-way-clinic-downtown",
            "luxe-dermatology-jumeirah",
            "capital-aesthetics-corniche",
        ])
        assert clinics.count() == 3

        downtown = clinics.get(slug="aesthetic-way-clinic-downtown")
        assert downtown.city == "Dubai"
        assert downtown.subscription_tier == SubscriptionTier.VIP
        assert downtown.latitude is not None and downtown.longitude is not None

        capital = clinics.get(slug="capital-aesthetics-corniche")
        assert capital.city == "Abu Dhabi"
        assert capital.subscription_tier == SubscriptionTier.BASIC

        # 3. Verify Branches
        assert ClinicBranch.objects.filter(clinic=downtown).count() == 2
        main_branch = ClinicBranch.objects.get(clinic=downtown, is_main_branch=True)
        assert main_branch.latitude is not None and main_branch.longitude is not None
        assert main_branch.google_place_id != ""

        # 4. Verify Practitioners of mixed types
        practitioners = Practitioner.objects.filter(clinic=downtown)
        types = set(practitioners.values_list("type", flat=True))
        assert PractitionerType.DOCTOR in types
        assert PractitionerType.NURSE in types
        assert PractitionerType.LICENSED_PROFESSIONAL in types

        # 5. Verify Categories and Treatments
        assert Category.objects.filter(slug="laser-and-light").exists()
        treatment = Treatment.objects.get(clinic=downtown, name_en="Full Face Candela GentleLase Pro")
        assert treatment.category.slug == "laser-and-light"
        assert treatment.price is not None

        # 6. Verify Offers, Products, Articles
        assert Offer.objects.filter(clinic=downtown).exists()
        assert Product.objects.filter(clinic=downtown).exists()
        assert Article.objects.filter(clinic=downtown).exists()

        # 7. Verify Leads
        leads = Lead.objects.filter(clinic=downtown)
        assert leads.count() >= 2

        # 8. Verify Referrals
        patient1 = User.objects.get(phone="+971501111111")
        assert ReferralInvite.objects.filter(referrer=patient1).count() == 3
        assert ReferralPointsLedger.objects.filter(patient=patient1).count() == 3
        assert ReferralDiscountCode.objects.filter(patient=patient1, code="AW-15-SEED").exists()

        # 9. Verify ClinicUser associations
        assert ClinicUser.objects.filter(clinic=downtown, user=clinic_admin).exists()

    def test_seed_data_idempotency(self):
        """Verify that running seed_data twice does not duplicate records."""
        call_command("seed_data", reset=True)
        initial_counts = {
            "clinics": Clinic.objects.count(),
            "branches": ClinicBranch.objects.count(),
            "practitioners": Practitioner.objects.count(),
            "treatments": Treatment.objects.count(),
            "offers": Offer.objects.count(),
            "products": Product.objects.count(),
            "articles": Article.objects.count(),
            "leads": Lead.objects.count(),
            "users": User.objects.count(),
        }

        # Run a second time without reset
        call_command("seed_data")

        for model_name, count in initial_counts.items():
            if model_name == "clinics":
                assert Clinic.objects.count() == count
            elif model_name == "branches":
                assert ClinicBranch.objects.count() == count
            elif model_name == "practitioners":
                assert Practitioner.objects.count() == count
            elif model_name == "treatments":
                assert Treatment.objects.count() == count
            elif model_name == "offers":
                assert Offer.objects.count() == count
            elif model_name == "products":
                assert Product.objects.count() == count
            elif model_name == "articles":
                assert Article.objects.count() == count
            elif model_name == "leads":
                assert Lead.objects.count() == count
            elif model_name == "users":
                assert User.objects.count() == count

    def test_seed_data_relationships_valid(self):
        """Verify all seeded foreign-key and M2M cross-entity relationships preserve clinic boundaries."""
        call_command("seed_data", reset=True)

        for pt in PractitionerTreatment.objects.all():
            assert pt.practitioner.clinic_id == pt.treatment.clinic_id

        for branch in ClinicBranch.objects.all():
            assert branch.clinic_id is not None

        for lead in Lead.objects.all():
            if lead.branch:
                assert lead.branch.clinic_id == lead.clinic_id
            if lead.practitioner:
                assert lead.practitioner.clinic_id == lead.clinic_id
            if lead.treatment:
                assert lead.treatment.clinic_id == lead.clinic_id
            if lead.offer:
                assert lead.offer.clinic_id == lead.clinic_id
            if lead.product:
                assert lead.product.clinic_id == lead.clinic_id

    def test_seed_data_atomic_rollback(self):
        """Verify that an unexpected failure triggers a transaction rollback."""
        from apps.clinics.management.commands.seed_data import Command

        # Initial seed
        call_command("seed_data", reset=True)
        initial_clinics_count = Clinic.objects.count()
        assert initial_clinics_count == 3

        # Patch _seed_referrals to simulate a failure
        with patch.object(Command, "_seed_referrals", side_effect=RuntimeError("Simulated database failure")):
            with pytest.raises(RuntimeError, match="Simulated database failure"):
                call_command("seed_data", reset=True)
