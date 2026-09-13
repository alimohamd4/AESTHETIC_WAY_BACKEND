"""
AESTHETIC WAY - Staging Seed Data Management Command
Specification Reference: Section 12 of AESTHETIC_WAY_Backend_Spec_v1.md

Seeds representative staging data for:
- Dubai and Abu Dhabi clinics across multiple subscription tiers (VIP, Featured, Basic)
- Multiple clinic branches with geographic coordinates and Google Maps integration
- Practitioners across multiple types (doctor, nurse, licensed_professional)
- Treatment categories and clinic-specific treatments linked via PractitionerTreatment
- Active promotional offers with date ranges
- Clinic products (inquiry only)
- Bilingual educational articles with author attribution
- Super Admin, Clinic Admins, and Clinic Staff accounts with role assignments
- Sample patient leads across lead types and statuses
- Referral invites, points ledger entries, and discount codes

Features:
- Idempotent: Can be run multiple times safely without generating uncontrolled duplicates.
- Uses transaction.atomic() for transactional integrity.
- Supports --reset option to clean previously seeded entities.
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import (
    ClinicRoleInClinic,
    ClinicUser,
    User,
    UserRole,
)
from apps.articles.models import Article
from apps.articles.models import ContentStatus as ArticleStatus
from apps.clinics.models import Clinic, ClinicBranch, ClinicStatus, SubscriptionTier
from apps.leads.models import Lead, LeadStatus, LeadType, PreferredTimeWindow
from apps.offers.models import Offer, OfferStatus
from apps.practitioners.models import (
    Practitioner,
    PractitionerStatus,
    PractitionerType,
)
from apps.products.models import ContentStatus as ProductStatus
from apps.products.models import Product
from apps.referrals.models import (
    DiscountCodeStatus,
    LedgerTransactionType,
    ReferralDiscountCode,
    ReferralInvite,
    ReferralInviteStatus,
    ReferralPointsLedger,
)
from apps.treatments.models import (
    Category,
    PractitionerTreatment,
    Treatment,
    TreatmentStatus,
)

STAGING_PASSWORD = "StagingPassword123!"


class Command(BaseCommand):
    help = "Seed staging data according to Section 12 of the specification"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reset and purge existing seed records before populating.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        reset = options.get("reset", False)
        self.stdout.write(self.style.NOTICE("==> Starting AESTHETIC WAY Staging Seed Data Generation..."))

        if reset:
            self.stdout.write(self.style.WARNING("Purging existing seeded entities (--reset specified)..."))
            self._purge_seeded_data()

        created_counts = {
            "users": 0,
            "clinics": 0,
            "branches": 0,
            "practitioners": 0,
            "categories": 0,
            "treatments": 0,
            "offers": 0,
            "products": 0,
            "articles": 0,
            "leads": 0,
            "referrals": 0,
        }

        # 1. Seed Users (Super Admin, Clinic Admins, Staff, Patients)
        users = self._seed_users(created_counts)

        # 2. Seed Clinics (Dubai VIP/Featured, Abu Dhabi Basic)
        clinics = self._seed_clinics(users, created_counts)

        # 3. Seed Branches
        branches = self._seed_branches(clinics, created_counts)

        # 4. Seed Practitioners
        practitioners = self._seed_practitioners(clinics, created_counts)

        # 5. Seed Categories & Treatments
        treatments = self._seed_catalog(clinics, practitioners, created_counts)

        # 6. Seed Offers
        offers = self._seed_offers(clinics, created_counts)

        # 7. Seed Products
        products = self._seed_products(clinics, created_counts)

        # 8. Seed Articles
        self._seed_articles(clinics, practitioners, created_counts)

        # 9. Seed Leads
        self._seed_leads(users, clinics, branches, practitioners, treatments, offers, products, created_counts)

        # 10. Seed Referral System
        self._seed_referrals(users, created_counts)

        self.stdout.write(self.style.SUCCESS("==> Seed Data Population Completed Successfully!"))
        for entity, count in created_counts.items():
            self.stdout.write(f"    - {entity.capitalize()}: {count} new/verified records")

    def _purge_seeded_data(self):
        """Purges seeded data cleanly while preserving non-seed entities."""
        seed_phones = [
            "+971500000001",
            "+971500000002",
            "+971500000003",
            "+971500000004",
            "+971501111111",
            "+971502222222",
        ]
        seed_clinic_slugs = [
            "aesthetic-way-clinic-downtown",
            "luxe-dermatology-jumeirah",
            "capital-aesthetics-corniche",
        ]
        Lead.objects.filter(clinic__slug__in=seed_clinic_slugs).delete()
        Offer.objects.filter(clinic__slug__in=seed_clinic_slugs).delete()
        Product.objects.filter(clinic__slug__in=seed_clinic_slugs).delete()
        Article.objects.filter(clinic__slug__in=seed_clinic_slugs).delete()
        Practitioner.objects.filter(clinic__slug__in=seed_clinic_slugs).delete()
        Treatment.objects.filter(clinic__slug__in=seed_clinic_slugs).delete()
        ClinicBranch.objects.filter(clinic__slug__in=seed_clinic_slugs).delete()
        ClinicUser.objects.filter(clinic__slug__in=seed_clinic_slugs).delete()
        Clinic.objects.filter(slug__in=seed_clinic_slugs).delete()
        ReferralDiscountCode.objects.filter(patient__phone__in=seed_phones).delete()
        ReferralPointsLedger.objects.filter(patient__phone__in=seed_phones).delete()
        ReferralInvite.objects.filter(referrer__phone__in=seed_phones).delete()
        User.objects.filter(phone__in=seed_phones).delete()

    def _seed_users(self, counts):
        users = {}
        user_specs = [
            {
                "key": "super_admin",
                "phone": "+971500000001",
                "email": "super_admin@aestheticway.ae",
                "full_name": "Super Admin",
                "role": UserRole.SUPER_ADMIN,
                "is_superuser": True,
                "is_staff": True,
            },
            {
                "key": "clinic_admin_downtown",
                "phone": "+971500000002",
                "email": "admin.downtown@aestheticway.ae",
                "full_name": "Dr. Sarah Al-Nuaimi",
                "role": UserRole.CLINIC_ADMIN,
                "is_superuser": False,
                "is_staff": False,
            },
            {
                "key": "clinic_admin_capital",
                "phone": "+971500000003",
                "email": "admin.capital@aestheticway.ae",
                "full_name": "Khaled Al-Qasimi",
                "role": UserRole.CLINIC_ADMIN,
                "is_superuser": False,
                "is_staff": False,
            },
            {
                "key": "clinic_staff_downtown",
                "phone": "+971500000004",
                "email": "staff.downtown@aestheticway.ae",
                "full_name": "Nour Hisham",
                "role": UserRole.CLINIC_STAFF,
                "is_superuser": False,
                "is_staff": False,
            },
            {
                "key": "patient_1",
                "phone": "+971501111111",
                "email": "patient1@aestheticway.ae",
                "full_name": "Layla Mansoor",
                "role": UserRole.PATIENT,
                "is_superuser": False,
                "is_staff": False,
            },
            {
                "key": "patient_2",
                "phone": "+971502222222",
                "email": "patient2@aestheticway.ae",
                "full_name": "Mariam Saleh",
                "role": UserRole.PATIENT,
                "is_superuser": False,
                "is_staff": False,
            },
        ]

        for spec in user_specs:
            user, created = User.objects.get_or_create(
                phone=spec["phone"],
                defaults={
                    "email": spec["email"],
                    "full_name": spec["full_name"],
                    "role": spec["role"],
                    "is_verified": True,
                    "is_active": True,
                    "is_superuser": spec["is_superuser"],
                    "is_staff": spec["is_staff"],
                },
            )
            if created or not user.has_usable_password():
                user.set_password(STAGING_PASSWORD)
                user.save()
            users[spec["key"]] = user
            if created:
                counts["users"] += 1
        return users

    def _seed_clinics(self, users, counts):
        clinics = {}
        clinic_specs = [
            {
                "key": "downtown",
                "slug": "aesthetic-way-clinic-downtown",
                "name_en": "Aesthetic Way Clinic Downtown",
                "name_ar": "عيادة إستيتك واي داون تاون",
                "city": "Dubai",
                "emirate": "Dubai",
                "address_en": "Sheikh Mohammed bin Rashid Blvd, Downtown Dubai",
                "address_ar": "بوليفارد الشيخ محمد بن راشد، وسط مدينة دبي",
                "phone": "+97144210001",
                "whatsapp": "+971504210001",
                "email": "info@aestheticway-downtown.ae",
                "website": "https://aestheticway-downtown.ae",
                "latitude": Decimal("25.1972000"),
                "longitude": Decimal("55.2744000"),
                "google_place_id": "ChIJb8EwA_NDXz4RD6fM2eJ_3q0",
                "google_maps_url": "https://maps.google.com/?q=25.1972,55.2744",
                "subscription_tier": SubscriptionTier.VIP,
                "status": ClinicStatus.ACTIVE,
                "is_featured": True,
                "display_order": 1,
                "google_rating": Decimal("4.9"),
                "admin_user": users["clinic_admin_downtown"],
                "staff_user": users["clinic_staff_downtown"],
            },
            {
                "key": "jumeirah",
                "slug": "luxe-dermatology-jumeirah",
                "name_en": "Luxe Dermatology Jumeirah",
                "name_ar": "لوكس للجلدية والتجميل جميرا",
                "city": "Dubai",
                "emirate": "Dubai",
                "address_en": "Jumeirah Beach Road, Jumeirah 1, Dubai",
                "address_ar": "شارع شاطئ جميرا، جميرا 1، دبي",
                "phone": "+97143440002",
                "whatsapp": "+971503440002",
                "email": "contact@luxederm-jumeirah.ae",
                "website": "https://luxederm-jumeirah.ae",
                "latitude": Decimal("25.2048000"),
                "longitude": Decimal("55.2708000"),
                "google_place_id": "ChIJb8EwA_NDXz4RD6fM2eJ_3q1",
                "google_maps_url": "https://maps.google.com/?q=25.2048,55.2708",
                "subscription_tier": SubscriptionTier.FEATURED,
                "status": ClinicStatus.ACTIVE,
                "is_featured": True,
                "display_order": 2,
                "google_rating": Decimal("4.8"),
                "admin_user": None,
                "staff_user": None,
            },
            {
                "key": "capital",
                "slug": "capital-aesthetics-corniche",
                "name_en": "Capital Aesthetics Corniche",
                "name_ar": "كابيتال للتجميل الكورنيش",
                "city": "Abu Dhabi",
                "emirate": "Abu Dhabi",
                "address_en": "Corniche Road West, Al Bateen, Abu Dhabi",
                "address_ar": "طريق الكورنيش الغربي، البطين، أبوظبي",
                "phone": "+97126810003",
                "whatsapp": "+971506810003",
                "email": "care@capitalaesthetics.ae",
                "website": "https://capitalaesthetics.ae",
                "latitude": Decimal("24.4672000"),
                "longitude": Decimal("54.3477000"),
                "google_place_id": "ChIJ3ZvZ3p7LXT4RB_f5V4qZ44k",
                "google_maps_url": "https://maps.google.com/?q=24.4672,54.3477",
                "subscription_tier": SubscriptionTier.BASIC,
                "status": ClinicStatus.ACTIVE,
                "is_featured": False,
                "display_order": 3,
                "google_rating": Decimal("4.7"),
                "admin_user": users["clinic_admin_capital"],
                "staff_user": None,
            },
        ]

        for spec in clinic_specs:
            clinic, created = Clinic.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "name_en": spec["name_en"],
                    "name_ar": spec["name_ar"],
                    "city": spec["city"],
                    "emirate": spec["emirate"],
                    "address_en": spec["address_en"],
                    "address_ar": spec["address_ar"],
                    "phone": spec["phone"],
                    "whatsapp": spec["whatsapp"],
                    "email": spec["email"],
                    "website": spec["website"],
                    "latitude": spec["latitude"],
                    "longitude": spec["longitude"],
                    "google_place_id": spec["google_place_id"],
                    "google_maps_url": spec["google_maps_url"],
                    "subscription_tier": spec["subscription_tier"],
                    "status": spec["status"],
                    "is_featured": spec["is_featured"],
                    "display_order": spec["display_order"],
                    "google_rating": spec["google_rating"],
                },
            )
            clinics[spec["key"]] = clinic
            if created:
                counts["clinics"] += 1

            # Associate Clinic Admins / Staff
            if spec["admin_user"]:
                ClinicUser.objects.get_or_create(
                    clinic=clinic,
                    user=spec["admin_user"],
                    defaults={"role_in_clinic": ClinicRoleInClinic.ADMIN, "is_active": True},
                )
            if spec["staff_user"]:
                ClinicUser.objects.get_or_create(
                    clinic=clinic,
                    user=spec["staff_user"],
                    defaults={"role_in_clinic": ClinicRoleInClinic.STAFF, "is_active": True},
                )
        return clinics

    def _seed_branches(self, clinics, counts):
        branches = {}
        branch_specs = [
            {
                "key": "downtown_main",
                "clinic": clinics["downtown"],
                "name_en": "Downtown Main Center",
                "name_ar": "الفرع الرئيسي داون تاون",
                "address_en": "Boulevard Plaza Tower 1, Level 4",
                "address_ar": "بوليفارد بلازا، البرج 1، الطابق 4",
                "city": "Dubai",
                "phone": "+97144210001",
                "latitude": Decimal("25.1972000"),
                "longitude": Decimal("55.2744000"),
                "google_place_id": "ChIJb8EwA_NDXz4RD6fM2eJ_3q0",
                "google_maps_url": "https://maps.google.com/?q=25.1972,55.2744",
                "is_main_branch": True,
            },
            {
                "key": "downtown_marina",
                "clinic": clinics["downtown"],
                "name_en": "Dubai Marina Branch",
                "name_ar": "فرع دبي مارينا",
                "address_en": "Marina Walk, Trident Grand Mall",
                "address_ar": "ممشى المارينا، ترايدنت جراند مول",
                "city": "Dubai",
                "phone": "+97144210005",
                "latitude": Decimal("25.0772000"),
                "longitude": Decimal("55.1332000"),
                "google_place_id": "ChIJz7w239zPXz4RS1gA53wQ83s",
                "google_maps_url": "https://maps.google.com/?q=25.0772,55.1332",
                "is_main_branch": False,
            },
            {
                "key": "jumeirah_main",
                "clinic": clinics["jumeirah"],
                "name_en": "Jumeirah Flagship Clinic",
                "name_ar": "فرع جميرا الرئيسي",
                "address_en": "Villa 42, Jumeirah Beach Road",
                "address_ar": "فيلا 42، شارع شاطئ جميرا",
                "city": "Dubai",
                "phone": "+97143440002",
                "latitude": Decimal("25.2048000"),
                "longitude": Decimal("55.2708000"),
                "google_place_id": "ChIJb8EwA_NDXz4RD6fM2eJ_3q1",
                "google_maps_url": "https://maps.google.com/?q=25.2048,55.2708",
                "is_main_branch": True,
            },
            {
                "key": "capital_main",
                "clinic": clinics["capital"],
                "name_en": "Corniche Prestige Branch",
                "name_ar": "فرع الكورنيش برستيج",
                "address_en": "Corniche Tower, Mezzanine Level",
                "address_ar": "برج الكورنيش، الميزانين",
                "city": "Abu Dhabi",
                "phone": "+97126810003",
                "latitude": Decimal("24.4672000"),
                "longitude": Decimal("54.3477000"),
                "google_place_id": "ChIJ3ZvZ3p7LXT4RB_f5V4qZ44k",
                "google_maps_url": "https://maps.google.com/?q=24.4672,54.3477",
                "is_main_branch": True,
            },
        ]

        for spec in branch_specs:
            branch, created = ClinicBranch.objects.get_or_create(
                clinic=spec["clinic"],
                name_en=spec["name_en"],
                defaults={
                    "name_ar": spec["name_ar"],
                    "address_en": spec["address_en"],
                    "address_ar": spec["address_ar"],
                    "city": spec["city"],
                    "phone": spec["phone"],
                    "latitude": spec["latitude"],
                    "longitude": spec["longitude"],
                    "google_place_id": spec["google_place_id"],
                    "google_maps_url": spec["google_maps_url"],
                    "is_main_branch": spec["is_main_branch"],
                    "is_active": True,
                },
            )
            branches[spec["key"]] = branch
            if created:
                counts["branches"] += 1
        return branches

    def _seed_practitioners(self, clinics, counts):
        practitioners = {}
        practitioner_specs = [
            {
                "key": "dr_noor",
                "clinic": clinics["downtown"],
                "type": PractitionerType.DOCTOR,
                "name_en": "Dr. Noor Al-Sabah",
                "name_ar": "د. نور الصباح",
                "title_en": "Consultant Dermatologist",
                "title_ar": "استشارية الأمراض الجلدية",
                "speciality_en": "Aesthetic Dermatology & Laser Surgery",
                "speciality_ar": "الجلدية التجميلية وجراحة الليزر",
                "status": PractitionerStatus.ACTIVE,
                "display_order": 1,
            },
            {
                "key": "nurse_maya",
                "clinic": clinics["downtown"],
                "type": PractitionerType.NURSE,
                "name_en": "Nurse Maya Lin",
                "name_ar": "الممرضة مايا لين",
                "title_en": "Senior Aesthetic Nurse",
                "title_ar": "أخصائية تمريض تجميلي",
                "speciality_en": "Skin Therapy & Medical Peels",
                "speciality_ar": "علاج البشرة والتقشير الطبي",
                "status": PractitionerStatus.ACTIVE,
                "display_order": 2,
            },
            {
                "key": "tech_sarah",
                "clinic": clinics["downtown"],
                "type": PractitionerType.LICENSED_PROFESSIONAL,
                "name_en": "Sarah Jenkins",
                "name_ar": "سارة جينكينز",
                "title_en": "Licensed Laser Specialist",
                "title_ar": "أخصائية ليزر معتمدة",
                "speciality_en": "Laser Hair Removal & Body Contouring",
                "speciality_ar": "إزالة الشعر بالليزر ونحت القوام",
                "status": PractitionerStatus.ACTIVE,
                "display_order": 3,
            },
            {
                "key": "dr_tariq",
                "clinic": clinics["jumeirah"],
                "type": PractitionerType.DOCTOR,
                "name_en": "Dr. Tariq Mansoor",
                "name_ar": "د. طارق منصور",
                "title_en": "Specialist Plastic Surgeon",
                "title_ar": "أخصائي جراحة التجميل",
                "speciality_en": "Facial Rejuvenation & Non-Surgical Lifting",
                "speciality_ar": "نضارة الوجه والشد غير الجراحي",
                "status": PractitionerStatus.ACTIVE,
                "display_order": 1,
            },
            {
                "key": "dr_omar",
                "clinic": clinics["capital"],
                "type": PractitionerType.DOCTOR,
                "name_en": "Dr. Omar Farooq",
                "name_ar": "د. عمر فاروق",
                "title_en": "Specialist Dermatologist",
                "title_ar": "أخصائي الأمراض الجلدية",
                "speciality_en": "Cosmetic Injectables & Anti-Aging",
                "speciality_ar": "الحقن التجميلية ومكافحة علامات التقدم بالسن",
                "status": PractitionerStatus.ACTIVE,
                "display_order": 1,
            },
        ]

        for spec in practitioner_specs:
            practitioner, created = Practitioner.objects.get_or_create(
                clinic=spec["clinic"],
                name_en=spec["name_en"],
                defaults={
                    "name_ar": spec["name_ar"],
                    "type": spec["type"],
                    "title_en": spec["title_en"],
                    "title_ar": spec["title_ar"],
                    "speciality_en": spec["speciality_en"],
                    "speciality_ar": spec["speciality_ar"],
                    "status": spec["status"],
                    "display_order": spec["display_order"],
                },
            )
            practitioners[spec["key"]] = practitioner
            if created:
                counts["practitioners"] += 1
        return practitioners

    def _seed_catalog(self, clinics, practitioners, counts):
        categories = {}
        cat_specs = [
            {"key": "laser", "slug": "laser-and-light", "name_en": "Laser & Light", "name_ar": "الليزر والضوء", "display_order": 1},
            {"key": "injectables", "slug": "injectables-and-fillers", "name_en": "Injectables & Fillers", "name_ar": "الحقن والفيلر", "display_order": 2},
            {"key": "skincare", "slug": "skin-rejuvenation", "name_en": "Skin Rejuvenation", "name_ar": "نضارة البشرة وتجديدها", "display_order": 3},
            {"key": "body", "slug": "body-contouring", "name_en": "Body Contouring", "name_ar": "نحت وتنسيق القوام", "display_order": 4},
        ]

        for spec in cat_specs:
            cat, created = Category.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "name_en": spec["name_en"],
                    "name_ar": spec["name_ar"],
                    "display_order": spec["display_order"],
                    "is_active": True,
                },
            )
            categories[spec["key"]] = cat
            if created:
                counts["categories"] += 1

        treatments = {}
        treatment_specs = [
            {
                "key": "gentlelase",
                "clinic": clinics["downtown"],
                "category": categories["laser"],
                "name_en": "Full Face Candela GentleLase Pro",
                "name_ar": "ليزر جنتل ليز برو للوجه بالكامل",
                "price": Decimal("450.00"),
                "practitioners": [practitioners["dr_noor"], practitioners["tech_sarah"]],
            },
            {
                "key": "hydrafacial",
                "clinic": clinics["downtown"],
                "category": categories["skincare"],
                "name_en": "HydraFacial Deluxe with LED Therapy",
                "name_ar": "هيدرافيشل ديلوكس مع العلاج بالضوء",
                "price": Decimal("850.00"),
                "practitioners": [practitioners["nurse_maya"]],
            },
            {
                "key": "profhilo_jumeirah",
                "clinic": clinics["jumeirah"],
                "category": categories["injectables"],
                "name_en": "Profhilo Bio-Remodeling 2ml",
                "name_ar": "بروفايلو لتجديد نضارة البشرة 2 مل",
                "price": Decimal("1800.00"),
                "practitioners": [practitioners["dr_tariq"]],
            },
            {
                "key": "botox_capital",
                "clinic": clinics["capital"],
                "category": categories["injectables"],
                "name_en": "Upper Face Anti-Wrinkle Treatment",
                "name_ar": "حقن البوتوكس للجزء العلوي من الوجه",
                "price": Decimal("1200.00"),
                "practitioners": [practitioners["dr_omar"]],
            },
        ]

        for spec in treatment_specs:
            treatment, created = Treatment.objects.get_or_create(
                clinic=spec["clinic"],
                name_en=spec["name_en"],
                defaults={
                    "name_ar": spec["name_ar"],
                    "category": spec["category"],
                    "price": spec["price"],
                    "status": TreatmentStatus.ACTIVE,
                    "is_active": True,
                },
            )
            treatments[spec["key"]] = treatment
            if created:
                counts["treatments"] += 1

            for p in spec["practitioners"]:
                PractitionerTreatment.objects.get_or_create(
                    practitioner=p,
                    treatment=treatment,
                )

        return treatments

    def _seed_offers(self, clinics, counts):
        offers = {}
        now = timezone.now()
        offer_specs = [
            {
                "key": "summer_glow",
                "clinic": clinics["downtown"],
                "title_en": "Summer Radiance Package (35% OFF)",
                "title_ar": "باقة إشراقة الصيف (خصم 35%)",
                "description_en": "Includes HydraFacial Deluxe + 1 GentleLase Session for smooth radiant skin.",
                "description_ar": "تشمل هيدرافيشل ديلوكس + جلسة جنتل ليز لنضارة فائقة.",
                "original_price": Decimal("1300.00"),
                "offer_price": Decimal("845.00"),
                "starts_at": now - timedelta(days=7),
                "ends_at": now + timedelta(days=23),
            },
            {
                "key": "profhilo_duo",
                "clinic": clinics["jumeirah"],
                "title_en": "Profhilo 2-Session Complete Protocol",
                "title_ar": "بروتوكول بروفايلو الكامل جلستان",
                "description_en": "Full two-session bioremodeling protocol for face and neck.",
                "description_ar": "البروتوكول الكامل لشد البشرة ونضارتها للوجه والرقبة.",
                "original_price": Decimal("3600.00"),
                "offer_price": Decimal("2850.00"),
                "starts_at": now - timedelta(days=3),
                "ends_at": now + timedelta(days=27),
            },
        ]

        for spec in offer_specs:
            offer, created = Offer.objects.get_or_create(
                clinic=spec["clinic"],
                title_en=spec["title_en"],
                defaults={
                    "title_ar": spec["title_ar"],
                    "description_en": spec["description_en"],
                    "description_ar": spec["description_ar"],
                    "original_price": spec["original_price"],
                    "offer_price": spec["offer_price"],
                    "starts_at": spec["starts_at"],
                    "ends_at": spec["ends_at"],
                    "status": OfferStatus.ACTIVE,
                    "is_active": True,
                },
            )
            offers[spec["key"]] = offer
            if created:
                counts["offers"] += 1
        return offers

    def _seed_products(self, clinics, counts):
        products = {}
        product_specs = [
            {
                "key": "sunscreen",
                "clinic": clinics["downtown"],
                "name_en": "Post-Procedure Soothing Mineral Fluid SPF 50+",
                "name_ar": "واقي شمس معدني مهدئ للبشرة بعد العلاج SPF 50+",
                "description_en": "Ultra-lightweight soothing sunscreen designed for post-laser sensitized skin.",
                "description_ar": "واقي شمسي خفيف ومهدئ مصمم خصيصاً للبشرة بعد جلسات الليزر.",
                "price": Decimal("195.00"),
            },
            {
                "key": "retinol",
                "clinic": clinics["jumeirah"],
                "name_en": "Advanced Cellular Retinol 0.5% Serum",
                "name_ar": "سيروم الريتينول المتقدم لتجديد خلايا البشرة 0.5%",
                "description_en": "Dermatologist-formulated nightly elixir for tone texture and renewal.",
                "description_ar": "إكسير ليلي مطور بإشراف أطباء الجلدية لتجديد البشرة.",
                "price": Decimal("320.00"),
            },
        ]

        for spec in product_specs:
            product, created = Product.objects.get_or_create(
                clinic=spec["clinic"],
                name_en=spec["name_en"],
                defaults={
                    "name_ar": spec["name_ar"],
                    "description_en": spec["description_en"],
                    "description_ar": spec["description_ar"],
                    "price": spec["price"],
                    "status": ProductStatus.ACTIVE,
                    "is_active": True,
                },
            )
            products[spec["key"]] = product
            if created:
                counts["products"] += 1
        return products

    def _seed_articles(self, clinics, practitioners, counts):
        article_specs = [
            {
                "slug": "laser-skin-prep-uae-climate",
                "clinic": clinics["downtown"],
                "author": practitioners["dr_noor"],
                "title_en": "Optimizing Laser Results in the UAE Climate",
                "title_ar": "كيفية الحصول على أفضل نتائج ليزر في مناخ الإمارات",
                "content_en": "Sun safety and hydration are vital before undergoing medical laser procedures in the GCC...",
                "content_ar": "الحماية من الشمس والترطيب الفائق ركنان أساسيان لنجاح جلسات الليزر الطبية في منطقة الخليج...",
            },
            {
                "slug": "bioremodeling-profhilo-guide",
                "clinic": clinics["jumeirah"],
                "author": practitioners["dr_tariq"],
                "title_en": "Bioremodeling Explained: What Makes Profhilo Unique?",
                "title_ar": "دليلك الشامل لتقنية البروفايلو وإعادة نضارة البشرة",
                "content_en": "Unlike traditional hyaluronic acid dermal fillers, bioremodeling stimulates collagen...",
                "content_ar": "على عكس فيلر حمض الهيالورونيك التقليدي، يعمل البروفايلو على تحفيز الكولاجين الطبيعي...",
            },
        ]

        for spec in article_specs:
            article, created = Article.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "clinic": spec["clinic"],
                    "author_practitioner": spec["author"],
                    "title_en": spec["title_en"],
                    "title_ar": spec["title_ar"],
                    "content_en": spec["content_en"],
                    "content_ar": spec["content_ar"],
                    "status": ArticleStatus.ACTIVE,
                    "is_published": True,
                    "published_at": timezone.now(),
                },
            )
            if not created and not article.is_published:
                article.is_published = True
                article.published_at = timezone.now()
                article.save(update_fields=["is_published", "published_at"])
            if created:
                counts["articles"] += 1

    def _seed_leads(self, users, clinics, branches, practitioners, treatments, offers, products, counts):
        lead_specs = [
            {
                "reference_code": "#REQ-88101",
                "clinic": clinics["downtown"],
                "branch": branches["downtown_main"],
                "patient": users["patient_1"],
                "practitioner": practitioners["dr_noor"],
                "treatment": treatments["gentlelase"],
                "offer": None,
                "product": None,
                "lead_type": LeadType.CONSULTATION,
                "status": LeadStatus.NEW,
                "patient_name": users["patient_1"].full_name,
                "patient_phone": users["patient_1"].phone,
                "patient_email": users["patient_1"].email,
                "preferred_time_window": PreferredTimeWindow.MORNING,
                "notes": "Consultation request for full face gentlelase.",
            },
            {
                "reference_code": "#REQ-88102",
                "clinic": clinics["downtown"],
                "branch": branches["downtown_marina"],
                "patient": users["patient_2"],
                "practitioner": None,
                "treatment": None,
                "offer": offers["summer_glow"],
                "product": None,
                "lead_type": LeadType.OFFER,
                "status": LeadStatus.CONTACTED,
                "patient_name": users["patient_2"].full_name,
                "patient_phone": users["patient_2"].phone,
                "patient_email": users["patient_2"].email,
                "preferred_time_window": PreferredTimeWindow.AFTERNOON,
                "notes": "Inquiring about booking the summer radiance package.",
            },
            {
                "reference_code": "#REQ-88103",
                "clinic": clinics["jumeirah"],
                "branch": branches["jumeirah_main"],
                "patient": None,  # Guest submission
                "practitioner": None,
                "treatment": None,
                "offer": None,
                "product": products["retinol"],
                "lead_type": LeadType.PRODUCT_INQUIRY,
                "status": LeadStatus.NEW,
                "patient_name": "Rashed Al-Marri",
                "patient_phone": "+971509998877",
                "patient_email": "guest.rashed@gmail.com",
                "preferred_time_window": PreferredTimeWindow.EVENING,
                "notes": "Interested in purchasing the Retinol Serum in-clinic.",
            },
        ]

        for spec in lead_specs:
            _, created = Lead.objects.get_or_create(
                reference_code=spec["reference_code"],
                defaults={
                    "clinic": spec["clinic"],
                    "branch": spec["branch"],
                    "patient": spec["patient"],
                    "practitioner": spec["practitioner"],
                    "treatment": spec["treatment"],
                    "offer": spec["offer"],
                    "product": spec["product"],
                    "lead_type": spec["lead_type"],
                    "status": spec["status"],
                    "patient_name": spec["patient_name"],
                    "patient_phone": spec["patient_phone"],
                    "patient_email": spec["patient_email"],
                    "preferred_time_window": spec["preferred_time_window"],
                    "notes": spec["notes"],
                    "consent_accepted": True,
                },
            )
            if created:
                counts["leads"] += 1

    def _seed_referrals(self, users, counts):
        patient1 = users["patient_1"]

        # Create sample invites for Patient 1
        invite_specs = [
            {"invitee_phone": "+971551000001", "status": ReferralInviteStatus.SUCCESSFUL},
            {"invitee_phone": "+971551000002", "status": ReferralInviteStatus.SUCCESSFUL},
            {"invitee_phone": "+971551000003", "status": ReferralInviteStatus.PENDING},
        ]

        for spec in invite_specs:
            _, created = ReferralInvite.objects.get_or_create(
                referrer=patient1,
                invitee_phone=spec["invitee_phone"],
                defaults={"status": spec["status"]},
            )
            if created:
                counts["referrals"] += 1

        # Ledger balance for Patient 1 (Milestone awards)
        ledger_specs = [
            {"points": 100, "tx_type": LedgerTransactionType.MILESTONE_20, "idempotency_key": "seed-milestone-20"},
            {"points": 175, "tx_type": LedgerTransactionType.MILESTONE_35, "idempotency_key": "seed-milestone-35"},
            {"points": 250, "tx_type": LedgerTransactionType.MILESTONE_50, "idempotency_key": "seed-milestone-50"},
        ]

        for spec in ledger_specs:
            _, created = ReferralPointsLedger.objects.get_or_create(
                idempotency_key=spec["idempotency_key"],
                defaults={"patient": patient1, "transaction_type": spec["tx_type"], "points": spec["points"]},
            )
            if created:
                counts["referrals"] += 1

        # Seed an active discount code
        code_str = "AW-15-SEED"
        _, created = ReferralDiscountCode.objects.get_or_create(
            code=code_str,
            defaults={
                "patient": patient1,
                "discount_percent": 15,
                "status": DiscountCodeStatus.AVAILABLE,
                "expires_at": timezone.now() + timedelta(days=90),
            },
        )
        if created:
            counts["referrals"] += 1
