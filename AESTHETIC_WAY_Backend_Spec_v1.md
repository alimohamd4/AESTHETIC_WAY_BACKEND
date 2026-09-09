# AESTHETIC WAY — Unified Backend Specification (v1 Production)

**Document type:** Production-oriented backend implementation spec  
**Product:** UAE aesthetic & dermatology clinic discovery + lead generation platform  
**Primary market:** United Arab Emirates (Dubai first, then other Emirates)  
**Client app:** Flutter (Patient + Clinic Portal + Super Admin)  
**Languages:** Arabic (RTL) + English (LTR)  
**Status:** Final unified spec for backend developer / coding AI  

---

## Table of contents

1. [Product non-negotiables](#1-product-non-negotiables)
2. [Roles](#2-roles)
3. [Screen inventory → APIs](#3-screen-inventory--apis)
4. [Core endpoints](#4-core-endpoints)
5. [Detailed API contracts](#5-detailed-api-contracts)
6. [Data models](#6-data-models)
7. [Server-side business rules](#7-server-side-business-rules)
8. [Security](#8-security)
9. [Notifications](#9-notifications)
10. [Analytics events](#10-analytics-events)
11. [Background jobs](#11-background-jobs)
12. [Seed data](#12-seed-data)
13. [Implementation phases](#13-implementation-phases)
14. [Out of scope (v1)](#14-out-of-scope-v1)
15. [Corrections vs earlier drafts](#15-corrections-vs-earlier-drafts)

---

## 1. Product non-negotiables

These rules are mandatory. Enforce them in API design, serializers, and business logic.

1. **No payments** — no payment gateway, cart, checkout, wallet, or stored value.
2. **Lead only** — appointment / offer / product request creates a Lead. The clinic contacts the patient outside the platform. No calendar slot booking and no final appointment confirmation inside the platform.
3. **Confirmation concept** — after lead submit, the product message is: the request has been sent and the clinic will contact the patient.
4. **Forbidden in patient-facing responses:**
   - DHA, DOH, MOHAP, Ministry of Health (or equivalent regulator names)
   - Clinic or doctor license numbers
   - Visible VIP / “diamond partner” badges for patients
5. **`subscription_tier` is internal only** — used for ranking (`vip` → `featured` → `basic`), never shown as a patient marketing badge.
6. **Offer duration is clinic-controlled** via `starts_at` / `ends_at`.
7. **No medical Before/After feature.**
8. **Platform support contact:** phone / WhatsApp = **`+971581989252`**
9. **Clinic contact numbers remain clinic-owned** (call/WhatsApp open clinic numbers, not the platform number).
10. **Referral (cumulative points):**
    - ≥ 20 successful invites → **+100** points  
    - ≥ 35 successful invites → **+175** points  
    - ≥ 50 successful invites → **+250** points  
    - At 50 invites, total points = **525**  
    - When points ≥ **500** → patient can **Collect** → generate code `AW-15-XXXX`  
    - Code meaning: **15% off original price** of treatments **not** included in an active offer; applied **in-clinic**  
    - Points do **not** expire quickly; user may redeem later  
11. **Doctor ratings inside the app are not required** for patients. Clinic rating may optionally be a Google-sourced display field only.
12. **No mandatory internal doctor reviews entity in v1.**

---

## 2. Roles

| Role | Description |
|------|-------------|
| `guest` | Browse public content; limited actions |
| `patient` | Profile, leads, referral, personal data |
| `clinic_staff` | Clinic-scoped operations (leads, verify codes) |
| `clinic_admin` | Full clinic portal for assigned clinic(s) |
| `super_admin` | Platform supervision, moderation, analytics |

Notes:
- Clinic users are scoped by `clinic_id`.
- Super Admin is **read-only** on lead operational status (clinic updates status).
- One primary role per account in v1 (except operational mapping for clinic staff under clinic_admin org if needed).

---

## 3. Screen inventory → APIs

Implement backend support for the current Flutter surfaces:

### Auth / entry
- Splash  
- Onboarding (local is fine; optional remote content)  
- Login  
- Register (optional referral code)  
- OTP verification  
- Forgot password / Reset password  

### Patient app
- Home feed (featured ranking, categories, offers, nearby clinics)  
- Clinics list + clinic profile  
- Treatments list + detail  
- Offers list + detail  
- Practitioners list + profile  
- Products list + detail  
- Articles list + detail  
- Appointment request (Lead) + success screen  
- My requests  
- Referral & rewards  
- Profile / settings / language / theme  
- Platform support (WhatsApp/call to `+971581989252`)  

### Clinic portal
- Dashboard  
- Leads list + lead detail + status update  
- Offers management  
- Clinic profile / branches / maps fields  
- Practitioners / treatments / products / articles management  
- Discount code verify + redeem  

### Super Admin
- Dashboard  
- Clinics supervision (status + subscription tier)  
- Analytics (engagement + referrals)  
- Content moderation (suspend/activate)  
- Settings (including platform support number)  
- Leads overview (**read-only**)  

### Shared
- Analytics event ingestion  
- Media upload (clinic/admin)  

---

## 4. Core endpoints

**Base URL (example):** `https://api.aestheticway.ae/api/v1`  

**Standard headers:**
- `Accept: application/json`
- `Content-Type: application/json`
- `Accept-Language: ar | en`
- `Authorization: Bearer <access_token>` when required

### Auth
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/verify-otp`
- `POST /auth/resend-otp`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET  /auth/me`

### App
- `GET /app/config`
- `GET /app/support-info` → must return **+971581989252**

### Discovery
- `GET /home/feed`
- `GET /categories`
- `GET /clinics`
- `GET /clinics/{id}`
- `GET /practitioners`
- `GET /practitioners/{id}`
- `GET /treatments`
- `GET /treatments/{id}`
- `GET /offers`
- `GET /offers/{id}`
- `GET /products`
- `GET /products/{id}`
- `GET /articles`
- `GET /articles/{id}`

### Leads
- `POST /leads`
- `GET  /leads/my`
- `GET  /leads/my/count`

### Referral
- `GET  /referral/my-status`
- `POST /referral/collect-code`

### Clinic portal
- `GET  /clinic-portal/dashboard`
- `GET  /clinic-portal/profile`
- `PUT  /clinic-portal/profile`
- Branches: list/create/update/delete as needed  
- Practitioners CRUD  
- Treatments CRUD  
- Offers CRUD  
- Products CRUD  
- Articles CRUD  
- `GET  /clinic-portal/leads`
- `GET  /clinic-portal/leads/{id}`
- `PATCH /clinic-portal/leads/{id}`
- `POST /clinic-portal/discount-codes/verify`
- `POST /clinic-portal/discount-codes/redeem`

### Admin
- `GET  /admin/dashboard`
- `GET  /admin/clinics`
- `GET  /admin/clinics/{id}`
- `PATCH /admin/clinics/{id}/status`
- `PATCH /admin/clinics/{id}/subscription`
- `GET  /admin/leads` (read-only)
- `GET  /admin/analytics/engagement`
- `GET  /admin/analytics/referrals`
- `GET  /admin/settings`
- `PUT  /admin/settings`
- Moderation endpoints for offers / products / articles (suspend/activate)

### Analytics & media
- `POST /analytics/events`
- `POST /media/upload`

---

## 5. Detailed API contracts

### 5.1 Auth

#### `POST /auth/register`
- Auth: none  
- Body:
```json
{
  "full_name": "Sara Al Mansoori",
  "phone": "+971501234567",
  "email": "sara@example.com",
  "password": "StrongPassword123!",
  "referral_code": "AW-DUBAI-88",
  "device_platform": "ios"
}
```
- Response `201`: user id + OTP challenged  
- Errors: `422` phone already used / invalid referral code  

#### `POST /auth/login`
- Body: `identifier` (phone or email) + `password`  
- Response `200`:
```json
{
  "token_type": "Bearer",
  "access_token": "eyJhbGciOi...",
  "refresh_token": "d7a8f9...",
  "expires_in": 3600,
  "user": {
    "id": "usr_991823",
    "full_name": "Sara Al Mansoori",
    "phone": "+971501234567",
    "email": "sara@example.com",
    "role": "patient"
  }
}
```
- Roles: `patient | clinic_admin | clinic_staff | super_admin`  
- Errors: `401` invalid credentials, `403` disabled account  

#### `POST /auth/verify-otp`
- Body: `phone`, `otp_code`, `purpose` (`registration | login | password_reset`)  
- Response `200`: tokens on success  

#### `POST /auth/resend-otp`
- Rate-limited (recommended: 1 request / 60 seconds per phone)  

#### `POST /auth/forgot-password` / `POST /auth/reset-password`
- OTP-based password reset  

#### `POST /auth/refresh` / `POST /auth/logout` / `GET /auth/me`
- Standard session lifecycle  

---

### 5.2 Home & discovery

#### `GET /home/feed`
- Auth: optional (guest allowed)  
- Query: `city`, `lat`, `lng`  
- Response sections:
  - `featured_ads` (ordered by internal tier; **do not send VIP label**)
  - `categories` (the 8 app categories)
  - `active_offers`
  - `nearby_clinics`

#### `GET /clinics`
- Query: `city`, `search`, `lat`, `lng`, `category_id`, `page`, `per_page`  
- Sort: internal tier → distance → rating  

#### `GET /clinics/{id}`
- Returns profile, branches, practitioners summary, services summary, maps URL, clinic phone/whatsapp  
- **Forbidden in response:** `subscription_tier`, license numbers  

#### `GET /practitioners` / `GET /practitioners/{id}`
- Include `type`: `doctor | nurse | licensed_professional`  
- **Forbidden:** `license_authority`, `license_number`  
- Do not expose an internal doctor-rating system to patients  

#### `GET /treatments` / `GET /treatments/{id}`
- No Before/After payloads  

#### `GET /offers` / `GET /offers/{id}`
- Include `original_price`, `offer_price`, `starts_at`, `ends_at`  
- Validity is clinic-controlled  

#### `GET /products` / `GET /products/{id}`
- Inquiry only — no purchase/checkout fields  

#### `GET /articles` / `GET /articles/{id}`
- Include author practitioner + clinic when published  

---

### 5.3 Leads

> Strict rule: this is lead capture only. No slot lock. No payment.

#### `POST /leads`
- Auth: patient (preferred)  
- Body example:
```json
{
  "clinic_id": "cl_101",
  "branch_id": "br_01",
  "lead_type": "consultation",
  "service_name": "Summer Glow Package",
  "practitioner_id": "pr_301",
  "patient_name": "Sara Al Mansoori",
  "patient_phone": "+971501234567",
  "patient_email": "sara@example.com",
  "preferred_time_window": "morning",
  "notes": "Prefer next week",
  "consent_accepted": true,
  "offer_id": null,
  "product_id": null
}
```
- `lead_type`: `consultation | offer | product_inquiry`  
- `preferred_time_window`: `morning | afternoon | evening`  
- Response `201`:
```json
{
  "success": true,
  "lead_reference": "#REQ-84920",
  "confirmation_message": "Your request has been sent and the clinic will contact you",
  "created_at": "2026-09-03T13:45:00Z"
}
```
- Errors: `422` if consent missing or required fields invalid  

#### `GET /leads/my`
- Patient leads with status `new | contacted | closed` and clinic contact fields  

#### `GET /leads/my/count`
- Optional badge count for patient navigation  

---

### 5.4 Referral

#### `GET /referral/my-status`
Return:
- `referral_code`
- `successful_invites_count`
- `current_points`
- `points_to_collect` (500)
- `can_collect_code`
- `points_expire`: `false`
- milestones: 20 / 35 / 50
- issued discount codes list (`available | used | expired`)

#### `POST /referral/collect-code`
- Requires points ≥ 500  
- Consumes 500 points  
- Creates `AW-15-XXXX`  
- Optional code expiry (e.g. 60 days) is allowed  
- **Points balance itself must not force quick expiry**

#### Clinic discount flow
- `POST /clinic-portal/discount-codes/verify`
- `POST /clinic-portal/discount-codes/redeem`  
  - single use  
  - store `redeemed_by_clinic_id` + timestamp  
  - reject already used/expired codes  

---

### 5.5 Support

#### `GET /app/support-info`
```json
{
  "platform_name": "AESTHETIC WAY",
  "support_phone": "+971581989252",
  "support_whatsapp": "+971581989252",
  "support_phone_display": "+971 58 198 9252"
}
```

---

### 5.6 Clinic portal (minimum behavior)

- Dashboard KPIs (leads, communication taps if available, redeemed codes)
- Leads list/detail
- `PATCH` lead status to `contacted` or `closed` + internal notes
- Update clinic profile/branches including Google Maps fields
- CRUD practitioners, treatments, offers, products, articles
- Discount verify/redeem

---

### 5.7 Super Admin (minimum behavior)

- Platform dashboard
- Clinics: activate/suspend, set subscription tier and validity dates
- Read-only leads overview
- Content moderation suspend/activate
- Engagement analytics per clinic
- Referral program stats
- Settings including platform support number

---

## 6. Data models

Minimum entities:

| Entity | Purpose |
|--------|---------|
| `users` | Auth identity + role |
| `patient_profiles` | Referral code, patient extras |
| `clinics` | Clinic directory + internal tier + geo + contacts |
| `clinic_branches` | Branches + maps |
| `clinic_users` | User ↔ clinic membership |
| `practitioners` | Doctors / nurses / licensed professionals |
| `treatments` | Services/procedures |
| `practitioner_treatments` | M2M |
| `offers` | Clinic offers with date window |
| `products` | Clinic products (inquiry only) |
| `articles` | Clinic educational content |
| `leads` | Appointment/offer/product requests |
| `referral_invites` | Successful invite graph |
| `referral_points_ledger` | Point deltas + reasons |
| `referral_discount_codes` | Collected 15% codes |
| `media_assets` | Uploaded images |
| `push_tokens` | FCM/APNs |
| `audit_logs` | Sensitive action trail |
| `app_settings` | Platform config (support number, etc.) |
| `analytics_events` and/or daily aggregates | KPIs |

### Important field rules

**clinics**
- Store `subscription_tier` internally: `vip | featured | basic`
- Store maps fields (`lat`, `lng`, `google_place_id` / maps URL)
- Do **not** expose tier label to patient APIs

**practitioners**
- `type`: `doctor | nurse | licensed_professional`
- If license fields exist in DB, keep them internal-only

**leads**
- `status`: `new | contacted | closed`
- `reference_code` unique (e.g. `#REQ-84920`)
- consent fields required on create
- `clinic_internal_notes` visible to clinic only

**referral_points_ledger**
- Prefer explicit ledger rows over fragile implicit-only math
- Reasons example: `milestone_20`, `milestone_35`, `milestone_50`, `collect_consume`, `admin_adjust`

**referral_discount_codes**
- `code` unique (`AW-15-XXXX`)
- `status`: `available | used | expired`
- `discount_percent` default `15`
- `redeemed_by_clinic_id` nullable

Do **not** implement a patient-facing internal doctor reviews system in v1.

---

## 7. Server-side business rules

1. **Clinic ranking:** subscription tier → distance → rating.  
2. **Serialization scrubbing:** never return `subscription_tier` or `license_*` on patient endpoints.  
3. **Lead create:** authenticated patient preferred. If guest leads are allowed, document the policy explicitly.  
4. **Lead status updates:** clinic only. Super Admin is read-only on lead operations.  
5. **Referral points:** awarded when invitee successfully registers with a valid referral code; write ledger entries.  
6. **Collect:** requires ≥ 500 points; consume 500; issue one code.  
7. **Redeem:** one-time; mark used with clinic + timestamp.  
8. **Offers active filter:** `starts_at <= now <= ends_at` and not suspended.  
9. **Rate limits:** OTP, login, lead creation.  
10. **Audit:** log admin suspend actions, subscription changes, and discount redeems.

### Referral math (authoritative)

```text
invites >= 20 → +100 points
invites >= 35 → +175 points
invites >= 50 → +250 points
At 50 invites: 100 + 175 + 250 = 525 points
Collect threshold: 500 points
```

### Lead status flow

```text
new → contacted → closed
```
Only clinic portal can advance status.

---

## 8. Security

- Password hashing: argon2 or bcrypt  
- JWT access token + refresh token (refresh rotation recommended)  
- RBAC middleware on every clinic/admin route  
- Clinic routes must enforce `clinic_id` scope  
- OTP rate limits and attempt limits  
- Lead spam limits per user/day  
- CORS locked to trusted app origins  
- Soft deletes where appropriate  
- Audit trail for sensitive actions  
- Never trust the client for points, ranking, or redeem validity — compute server-side  

---

## 9. Notifications

| Event | Recipient | Channel (v1 target) |
|-------|-----------|---------------------|
| New lead | Clinic | Push (+ optional email) |
| Lead submitted confirmation | Patient | Push (+ optional SMS) |
| Referral milestone reached | Patient | Push (optional) |
| Discount code collected | Patient | Push (optional) |
| Discount code redeemed | Patient | Push (optional) |

OTP delivery via an SMS provider suitable for UAE numbers.

---

## 10. Analytics events

### `POST /analytics/events`
Auth optional (support `anonymous_id` for guests)

Example body:
```json
{
  "event_type": "whatsapp_tap",
  "clinic_id": "cl_101",
  "metadata": {
    "source_screen": "clinic_profile",
    "city": "Dubai"
  }
}
```

Supported event types:
- `app_open`
- `clinic_view`
- `whatsapp_tap`
- `call_tap`
- `maps_tap`
- `lead_submitted`

Admin analytics should aggregate per clinic over day/week/month:
- profile views
- WhatsApp taps
- call taps
- leads count
- contacted conversion rate
- referral conversions

---

## 11. Background jobs

- Mark offers expired when `ends_at` has passed  
- Optionally expire unused discount codes when `expires_at` is set  
- Nightly analytics rollups  
- Optional cleanup of revoked refresh tokens  

---

## 12. Seed data

Staging seed should include:
- Clinics in Dubai / Abu Dhabi with different subscription tiers  
- Branches with maps fields  
- Practitioners of mixed types  
- Treatments, offers, products, articles  
- One super admin  
- At least one clinic_admin per sample clinic  
- Sample leads  
- Sample referral codes / invites  

---

## 13. Implementation phases

### Phase 1 — Infrastructure, auth, roles
- Project bootstrap, DB, migrations  
- Users/roles, JWT, OTP flow  
- **DoD:** register/login/OTP/reset works with role-aware tokens  

### Phase 2 — Discovery catalog
- Clinics, branches, practitioners, treatments, offers, products, articles  
- Home feed + ranking  
- Forbidden-field scrubbing  
- **DoD:** public discovery endpoints correct in AR/EN intent and ranking  

### Phase 3 — Leads + clinic portal
- Create lead + reference code  
- Clinic lead inbox + status updates  
- Clinic content management  
- **DoD:** full loop patient submits lead → clinic sees and updates status  

### Phase 4 — Referral + admin + launch prep
- Referral ledger, collect, verify, redeem  
- Admin dashboard, clinic suspension, tier management, analytics  
- Support settings (`+971581989252`)  
- Media upload  
- **DoD:** referral collect/redeem works; admin KPIs available; Flutter can replace mocks  

### Phase 5 — Hardening
- Rate limits, audit logs, seed data, staging deploy, basic load checks  

---

## 14. Out of scope (v1)

Do **not** build in v1:
- Payment gateways / checkout / invoices  
- Calendar slot booking / appointment confirmation engine  
- E-commerce cart for products  
- Home services  
- Non-medical salon marketplace  
- Medical Before/After clinical photo workflows  
- UAE Pass integration  
- In-app doctor review system as a core module  

---

## 15. Corrections vs earlier drafts

Apply these corrections if any older draft conflicts:

1. Clinics **own** products — users do not “sell” products.  
2. Do not return internal practitioner ratings to patients.  
3. Explicitly implement clinic CRUD for treatments, products, and articles (not only a generic profile endpoint).  
4. Admin must be able to moderate/suspend content, not only clinics.  
5. Prefer a **points ledger** over implicit-only point math.  
6. Favorites endpoints only if the mobile UI actually includes favorites; otherwise defer.  
7. No Before/After module.  
8. Platform support number is fixed: **+971581989252**.  

---

## Final instruction to the implementer

Implement the backend against **this document as the source of truth**.

If Flutter mock services conflict with these rules:
- **these product rules win**
- then match real app screens and flows

Deliverables expected from backend work:
- Migrated schema  
- Role-protected APIs  
- Seeded staging environment  
- API documentation (OpenAPI preferred)  
- Test coverage for auth, leads, referral collect/redeem, and permission boundaries  
```

