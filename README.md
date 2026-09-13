# AESTHETIC WAY Backend

## Overview

AESTHETIC WAY Backend is a high-performance Django REST Framework backend powering the **AESTHETIC WAY** aesthetic and dermatology clinic discovery platform in the United Arab Emirates (Dubai and other Emirates).

The platform connects patients with licensed aesthetic and dermatology clinics, certified practitioners, and treatments. The v1 architecture is intentionally **lead-based**. In accordance with the authoritative specification (`AESTHETIC_WAY_Backend_Spec_v1.md`), this system intentionally does **NOT** implement:
- Payments, payment gateways, or invoices
- Checkout workflows
- E-commerce shopping carts
- Stored-value wallets or digital balances
- Direct calendar slot locking or in-app appointment scheduling
- UAE Pass integration
- Medical Before/After photo galleries or workflows
- In-app doctor review or rating systems

All inquiries create structured **Leads**. Final consultation booking, scheduling, and payment handling take place directly between the clinic and patient outside the platform.

---

## Technology Stack

- **Language:** Python 3.13
- **Web Framework:** Django 5.2 & Django REST Framework (DRF)
- **Database:** PostgreSQL (production target with PostGIS support) / SQLite (local development & testing)
- **Caching & Broker:** Redis
- **Asynchronous Task Processing:** Celery & Celery Beat
- **Authentication:** JSON Web Tokens (JWT via `djangorestframework-simplejwt`) with refresh token rotation and token blacklist
- **Password Hashing:** Argon2 (`argon2-cffi`) with PBKDF2 fallback
- **Image Processing & Validation:** Pillow
- **API Documentation:** OpenAPI 3.0 via `drf-spectacular` (Swagger UI & ReDoc)
- **Testing:** `pytest`, `pytest-django`, `pytest-cov`, `Faker`

---

## Architecture

The backend is organized into domain-driven Django applications under the `apps/` namespace:

- **`accounts`**: Custom user identity model, role-based access control, OTP generation and verification, patient profiles, and clinic user memberships.
- **`clinics`**: Clinic directory, multiple branch management with geographic coordinates and Google Maps integration, operating hours, and internal subscription tier attributes.
- **`practitioners`**: Medical practitioners (doctors, nurses, licensed professionals) linked to clinics and treatments.
- **`treatments`**: Procedure catalog, treatment categories, pricing, and practitioner-treatment assignments.
- **`offers`**: Clinic-controlled promotional campaigns with active date ranges (`starts_at` / `ends_at`).
- **`products`**: Skincare and aesthetic clinic inventory (inquiry only; no purchasing).
- **`articles`**: Bilingual educational articles authored by practitioners or the platform.
- **`leads`**: Centralized lead capture, patient request tracking, duplicate submission protection, and clinic workflow management.
- **`referrals`**: Cumulative invite progression ladder, points ledger, discount code issuance, and clinic-level code verification/redemption.
- **`analytics`**: Privacy-focused event ingestion (`app_open`, `clinic_view`, `whatsapp_tap`, `call_tap`, `maps_tap`, `lead_submitted`) and clinic KPI rollups.
- **`notifications`**: Multi-channel notification pipeline (Push, SMS, Email) with asynchronous queueing.
- **`media`**: Secure file upload handling, magic-byte inspection, MIME verification, and media asset storage.
- **`app_config`**: Platform runtime settings, dynamic support information, and mobile app minimum versioning.
- **`admin_portal`**: Super Admin supervision, clinic approvals, content moderation, and platform auditing.
- **`home`**: Aggregated, geo-cached mobile home discovery feed.

### API Separation & Tenant Isolation
The API provides three distinct operational surfaces:
1. **Patient APIs** (`/api/v1/...`): Public discovery, authentication, profile management, lead submission, and referral rewards.
2. **Clinic Portal APIs** (`/api/v1/clinic-portal/...`): Scoped strictly to authenticated `clinic_admin` and `clinic_staff` users for their assigned clinic (`clinic_id`). Enforces database-level tenant isolation, IDOR prevention, lead management, and discount code redemption.
3. **Super Admin APIs** (`/api/v1/admin/...`): Platform-wide management for `super_admin` users, including clinic suspension/activation, tier assignment, content moderation, analytics, settings, and read-only lead supervision.

---

## Authentication

Authentication is token-based using JWT with short-lived access tokens (1 hour) and refresh token rotation.

### Supported Flows
- **Registration** (`POST /api/v1/auth/register/`): Accepts patient details, phone number, password, and optional `referral_code`. Triggers an SMS OTP challenge.
- **Login** (`POST /api/v1/auth/login/`): Accepts an `identifier` (phone number or email address) and `password`:
  ```json
  {
    "identifier": "+971501234567",
    "password": "StrongPassword123!"
  }
  ```
  *(The legacy `"phone"` field remains supported for backward compatibility).*
- **OTP Verification** (`POST /api/v1/auth/verify-otp/`): Verifies the 4-digit OTP for `registration`, `login`, or `password_reset`. Upon registration verification, pending referral invites are atomically processed.
- **OTP Resend** (`POST /api/v1/auth/resend-otp/`): Rate-limited to 1 request per 60 seconds per phone number.
- **Password Reset** (`POST /api/v1/auth/forgot-password/` and `POST /api/v1/auth/reset-password/`): OTP-gated credential reset.
- **Token Refresh & Rotation** (`POST /api/v1/auth/refresh/`): Returns a new access token and a rotated refresh token.
- **Logout** (`POST /api/v1/auth/logout/`): Blacklists the active refresh token.
- **Current User Profile** (`GET /api/v1/auth/me/`): Returns user profile and associated role claims.

---

## Referral System

The platform features a cumulative, milestone-based referral rewards program:

### Milestone Progression Ladder
- **$\ge$ 20 successful invites:** +100 points
- **$\ge$ 35 successful invites:** +175 points
- **$\ge$ 50 successful invites:** +250 points
- **Total at 50 invites:** **525 points**

### Discount Code Collection
- When a patient reaches **500 points**, they can invoke `POST /api/v1/referral/collect-code/`.
- Consumes 500 points via an explicit atomic ledger transaction (`ReferralPointsLedger`).
- Issues a unique discount code formatted as `AW-15-XXXX` (providing 15% off original prices for non-offer treatments).
- Code statuses: `available`, `used`, `expired`.
- Referral points do not expire quickly.

### Security & In-Clinic Flow
- **Attribution Gating:** Referral invites are attributed strictly **after** successful OTP verification of the invitee.
- **Fraud Prevention:** Atomic `select_for_update()` transaction locking prevents race conditions, self-referrals, and duplicate awards.
- **Clinic Verification:** Clinics verify codes via `POST /api/v1/clinic-portal/discount-codes/verify/`.
- **Atomic Redemption:** Clinics redeem codes in-clinic via `POST /api/v1/clinic-portal/discount-codes/redeem/`, marking the code `used` and logging an immutable audit record.

---

## Lead System

The lead pipeline coordinates patient interest with clinic outreach:

1. **Submission** (`POST /api/v1/leads/`): Patient submits an inquiry for a consultation, offer, or product.
2. **Immediate Confirmation:** Patient receives `#REQ-XXXXX` and the authoritative message:
   *"Your request has been sent and the clinic will contact you"*.
3. **Clinic Inbox:** The designated clinic receives the lead in their portal inbox (`GET /api/v1/clinic-portal/leads/`).
4. **Status Progression:** Clinic staff update the operational status (`PATCH /api/v1/clinic-portal/leads/{id}/`):
   `new` $\rightarrow$ `contacted` $\rightarrow$ `closed`.
5. **Super Admin Supervision:** Super Admins can monitor leads across all clinics via `GET /api/v1/admin/leads/`, but are strictly **read-only** (cannot mutate operational lead status).
6. **Anti-Spam:** Rate throttling and duplicate detection block redundant requests for the same service within 24 hours.

*Note: This is strictly lead generation and triage; no calendar booking or slot reservation occurs within the application.*

---

## Discovery APIs

Public catalog endpoints allow patients and guests to browse medical aesthetic services across the UAE:

- **Home Feed** (`GET /api/v1/home/feed/`): Featured ads, category list, active promotional offers, and nearby clinics.
- **Categories** (`GET /api/v1/categories/`): Standard medical aesthetic procedure categories.
- **Clinics** (`GET /api/v1/clinics/` and `GET /api/v1/clinics/{id}/`): Full profiles, multiple branches, Google Maps URLs, direct clinic phone/WhatsApp contacts, and active staff.
- **Practitioners** (`GET /api/v1/practitioners/` and `GET /api/v1/practitioners/{id}/`): Medical team profiles (`doctor`, `nurse`, `licensed_professional`).
- **Treatments** (`GET /api/v1/treatments/` and `GET /api/v1/treatments/{id}/`): Catalog of procedures with pricing and category filters.
- **Offers** (`GET /api/v1/offers/` and `GET /api/v1/offers/{id}/`): Time-limited clinic promotional packages.
- **Products** (`GET /api/v1/products/` and `GET /api/v1/products/{id}/`): Clinic skincare products (inquiry only).
- **Articles** (`GET /api/v1/articles/` and `GET /api/v1/articles/{id}/`): Published educational and post-procedure articles.

### Ranking & Field Scrubbing Rules
- **Ranking Hierarchy:** Internal subscription tier (`vip` $\rightarrow$ `featured` $\rightarrow$ `basic`) $\rightarrow$ geographic distance (via PostGIS / coordinates) $\rightarrow$ Google rating.
- **Strict Privacy & Regulator Scrubbing:** Public serializers completely exclude `subscription_tier` (never displayed to patients), license numbers, DHA/DOH/MOHAP regulator tags, and internal moderation notes.

---

## Clinic Portal

Clinic staff and administrators manage their facility's presence and patient intake through scoped portal endpoints:

- **Dashboard** (`GET /api/v1/clinic-portal/dashboard/`): Real-time KPIs (lead conversion rate, communication taps, redeemed discount codes, active catalog counts).
- **Profile & Branches** (`GET/PUT /api/v1/clinic-portal/profile/`, `/branches/`): Contact details, geocodes, Google Place IDs, and main branch flags.
- **Catalog Management**: Full CRUD for practitioners, treatments, offers, products, and articles.
- **Lead Inbox**: List, filter, retrieve, and update operational statuses (`new`, `contacted`, `closed`) and internal clinic notes.
- **Discount Code Tools**: Verify and redeem patient 15% discount codes.

**Tenant Isolation:** All queries filter by `clinic_id__in=user.clinic_memberships`. Cross-clinic access attempts result in `403 Forbidden` or `404 Not Found`.

---

## Super Admin Portal

Super Admin endpoints provide oversight and governance:

- **Platform Dashboard** (`GET /api/v1/admin/dashboard/`): Global clinic counts, patient statistics, total leads, conversion percentage, and referral metrics.
- **Clinic Governance** (`/api/v1/admin/clinics/`): Approve, activate, or suspend clinics, and assign subscription tiers (`vip`, `featured`, `basic`).
- **Content Moderation**: Review and suspend/activate offers, products, and articles.
- **Analytics Aggregations**: Engagement metrics (profile views, call taps, WhatsApp taps, map taps) and referral milestones.
- **Platform Configuration** (`GET/PUT /api/v1/admin/settings/`): Configure platform parameters, including support contact numbers.
- **Audit Logs** (`GET /api/v1/admin/audit-logs/`): Read-only log of sensitive administrative actions (suspensions, tier updates, redemptions).

---

## Media Security

Media uploads (`POST /api/v1/media/upload/`) enforce multi-layer security:

- **Size Limit:** Maximum 5 MB per file.
- **Extension Whitelist:** Strictly `.jpg`, `.jpeg`, `.png`, `.webp`.
- **MIME & Header Validation:** Uploaded `Content-Type` must match allowed image types.
- **Magic-Byte Inspection:** Binary header inspection confirms file signature (`\xFF\xD8\xFF`, `\x89PNG`, `RIFF...WEBP`).
- **Pillow Stream Verification:** Image is parsed with `PIL.Image.verify()` to detect malformed files, corrupted headers, and polyglot scripts.
- **Path Traversal & Null-Byte Scrubbing:** Filenames are stripped of directory separators and null bytes (`\x00`).
- **Executable Blocking:** All script and executable formats (`.php`, `.py`, `.exe`, `.sh`, `.svg`, etc.) are blocked.

---

## Notifications and Celery

The platform includes a notification dispatch system and periodic background task suite:

### Notification Engine
- Dispatches event-driven notifications (`new_lead_clinic`, `lead_confirmation_patient`, `referral_milestone`, `discount_collected`, `discount_redeemed`).
- Configured with `apply_async(..., retry=False)` so offline message brokers fail fast without stalling HTTP request-response cycles.

### Celery Beat Periodic Schedules
- **`offers.expire_stale_offers`**: Runs hourly; deactivates expired offers where `ends_at < now`.
- **`referrals.expire_stale_discount_codes`**: Runs every 6 hours; marks stale discount codes past `expires_at` as `expired`.
- **`analytics.daily_rollup`**: Runs nightly at 01:00 (Asia/Dubai); aggregates clinic analytics.
- **`core.cleanup_revoked_refresh_tokens`**: Runs nightly at 02:00 (Asia/Dubai); cleans expired blacklisted JWTs.

*(Note: Live asynchronous execution requires a running Redis broker. During automated test runs, `CELERY_TASK_ALWAYS_EAGER = True` is used).*

---

## Analytics

Privacy-focused event tracking via `POST /api/v1/analytics/events/`:

- **Supported Event Types:** `app_open`, `clinic_view`, `whatsapp_tap`, `call_tap`, `maps_tap`, `lead_submitted`.
- **Guest & User Tracking:** Supports both authenticated `user` references and guest `anonymous_id` identifiers.
- **Clinic Attribution:** Events link to specific clinics to generate aggregated engagement reports for clinic staff and platform administrators.

---

## Localization

The backend is built for bilingual English and Arabic operations:

- **Header Negotiation:** Inspects incoming `Accept-Language` headers (`ar` or `en`).
- **Django Middleware:** `django.middleware.locale.LocaleMiddleware` active in request processing.
- **Bilingual Schema:** Core entities include bilingual database fields (`name_en` / `name_ar`, `description_en` / `description_ar`, `title_en` / `title_ar`, `bio_en` / `bio_ar`).
- **RTL / LTR Support:** Field values preserve bidirectional typography for seamless Flutter client rendering.

---

## API Base URL

All REST API endpoints are served under the `/api/v1/` prefix:

```text
/api/v1/
├── auth/
├── home/
├── clinics/
├── practitioners/
├── treatments/
├── categories/
├── offers/
├── products/
├── articles/
├── leads/
├── referral/
├── analytics/
├── media/
├── app/
├── clinic-portal/
└── admin/
```

Interactive API documentation:
- **Swagger UI:** `/api/docs/`
- **ReDoc:** `/api/redoc/`
- **OpenAPI 3 Schema:** `/api/schema/`

---

## Development Setup

### Prerequisites
- Python 3.13+
- Git

### Installation (Windows PowerShell)

1. **Clone the repository:**
   ```powershell
   git clone https://github.com/alimohamd4/AESTHETIC_WAY_BACKEND.git
   cd AESTHETIC_WAY_BACKEND
   ```

2. **Create and activate a virtual environment:**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```powershell
   Copy-Item .env.example .env
   ```
   *(Review and update `.env` as needed).*

5. **Apply database migrations:**
   ```powershell
   python manage.py migrate
   ```

6. **Verify the installation:**
   ```powershell
   python manage.py check
   ```

7. **Start the development server:**
   ```powershell
   python manage.py runserver
   ```

---

## Testing

Run the automated test suite and integrity checks:

```powershell
# Run all unit, integration, and security tests
pytest -q

# Verify Django system integrity
python manage.py check

# Confirm no uncommitted schema changes
python manage.py makemigrations --check --dry-run
```

---

## Seed Data

To populate the development database with representative staging data for Dubai and Abu Dhabi:

```powershell
python manage.py seed_data
```

The seed command is **idempotent** and safe to run multiple times. It populates:
- Sample clinics in Dubai and Abu Dhabi across VIP, Featured, and Basic tiers
- Clinic branches with coordinates and Google Maps integration
- Practitioners, categories, treatments, active offers, products, and published articles
- Super Admin, Clinic Admin, and Clinic Staff accounts
- Sample leads and referral codes

---

## Production Deployment Notes

In a production environment:
- **Database:** Deploy with PostgreSQL 15+ and PostGIS. Set `DATABASE_URL` or `DB_*` variables.
- **Cache & Task Broker:** Run a dedicated Redis 7+ instance.
- **Application Server:** Run Django under Gunicorn or Uvicorn behind an Nginx reverse proxy with HTTPS/TLS termination.
- **Background Workers:** Execute Celery worker (`celery -A config worker -l info`) and Celery Beat (`celery -A config beat -l info`).
- **Media Storage:** Configure S3 or compatible object storage (`USE_S3=True`).
- **Secrets:** Inject secrets via container environment variables; never commit `.env` files.

---

## Security

- **Argon2 Password Hashing:** Industry-standard password hashing algorithm.
- **JWT Protection:** Refresh token rotation and token blacklist prevent replay attacks.
- **Rate Limiting:** Granular throttling on OTP endpoints (1/min, 5/hour) and lead generation (10/hour).
- **Tenant Isolation:** Multi-tenant scoping on all clinic portal endpoints.
- **Media Hardening:** Multi-layer validation prevents executable injection and path traversal.
- **CORS & Host Whitelisting:** Controlled through `CORS_ALLOWED_ORIGINS` and `ALLOWED_HOSTS`.

---

## Specification Compliance

This backend has been audited and verified against **`AESTHETIC_WAY_Backend_Spec_v1.md`**:

- **Automated Tests:** **332 passed, 0 failed**
- **Django System Check:** **0 issues**
- **Migration Sync:** **No pending changes**
- **Seed Data:** **Executes idempotently (Exit Code 0)**
- **Forbidden v1 Features:** **100% absent** (no payments, carts, slots, UAE Pass, Before/After, doctor reviews)

*(Note: Live Redis broker and Celery worker execution must be provisioned in the production deployment infrastructure; tasks are verified via eager execution in testing).*

---

## Repository Structure

```text
AESTHETIC_WAY_BACKEND/
├── api/
│   └── v1/urls.py
├── apps/
│   ├── accounts/
│   ├── admin_portal/
│   ├── analytics/
│   ├── app_config/
│   ├── articles/
│   ├── clinics/
│   ├── home/
│   ├── leads/
│   ├── media/
│   ├── notifications/
│   ├── offers/
│   ├── practitioners/
│   ├── products/
│   ├── referrals/
│   └── treatments/
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── testing.py
│   │   └── production.py
│   ├── asgi.py
│   ├── celery.py
│   ├── urls.py
│   └── wsgi.py
├── core/
│   ├── exceptions/
│   ├── health/
│   ├── pagination/
│   ├── permissions/
│   ├── tasks.py
│   └── throttles.py
├── docker/
├── docker-compose.yml
├── manage.py
├── requirements.txt
├── pytest.ini
├── .env.example
├── .gitignore
├── AESTHETIC_WAY_Backend_Spec_v1.md
└── README.md
```

---

## License

License: Not yet specified.
