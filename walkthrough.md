# Walkthrough: Secure Media Handling Implementation

We have designed, implemented, and verified a secure media handling subsystem for the **AESTHETIC WAY** platform.

---

## 1. Overview of Changes

### Media Types & Scoping
Implemented the 8 required media types in [`MediaType`](file:///c:/Users/Ali/Desktop/AESTHETIC_WAY_BACKEND/apps/media/models.py#L38):
1. `clinic_logo` (Clinic)
2. `clinic_cover` (Clinic)
3. `clinic_gallery` (Clinic)
4. `practitioner_avatar` (Clinic)
5. `product_image` (Clinic)
6. `article_cover` (Clinic / Platform)
7. `offer_image` (Clinic)
8. `patient_profile_image` (Patient)

### Key Components Added

#### 1. Security Validation Pipeline ([`apps/media/validators.py`](file:///c:/Users/Ali/Desktop/AESTHETIC_WAY_BACKEND/apps/media/validators.py))
- **Size Validation:** Capped at 5MB (`MAX_MEDIA_FILE_SIZE_BYTES = 5 * 1024 * 1024`). Rejects empty files and files > 5MB.
- **Extension Whitelist:** Strictly permits `.jpg`, `.jpeg`, `.png`, `.webp`.
- **Dangerous Extensions Blacklist:** Explicitly checks and blocks dangerous files (`.exe`, `.sh`, `.bat`, `.php`, `.svg`, `.html`, scripts).
- **MIME Type Validation:** Verifies `image/jpeg`, `image/png`, `image/webp`.
- **Magic Bytes Inspection:** Inspects raw stream headers (e.g. `\xFF\xD8\xFF` for JPEG, `\x89PNG` for PNG, `RIFF...WEBP` for WebP).
- **Pillow Stream Integrity:** Runs `img.verify()` and format checking to detect corrupt images, embedded polyglots, and disguised scripts (e.g. `.exe` renamed to `.jpg`).
- **Filename Sanitization:** Strips path traversal sequences (`../`, null bytes) and special characters.

#### 2. Model & Storage Abstraction ([`apps/media/models.py`](file:///c:/Users/Ali/Desktop/AESTHETIC_WAY_BACKEND/apps/media/models.py))
- Created [`MediaAsset`](file:///c:/Users/Ali/Desktop/AESTHETIC_WAY_BACKEND/apps/media/models.py#L82):
  - Stores metadata only in PostgreSQL (`id`, `media_type`, `original_filename`, `file_size`, `mime_type`, `width`, `height`, `uploader`, `clinic`, `created_at`).
  - Binary files are **never** stored in PostgreSQL. Instead, `file = models.FileField(upload_to=media_asset_upload_path)` delegates to the configured storage backend (`FileSystemStorage` locally, `S3Boto3Storage` in production).
  - Storage path partition: `media_assets/{clinics|users|platform}/{id}/{media_type}/{YYYY}/{MM}/{uuid}.{ext}`.
  - Automatic cleanup: [`cleanup_media_file_on_delete`](file:///c:/Users/Ali/Desktop/AESTHETIC_WAY_BACKEND/apps/media/models.py#L141) signal removes files from the storage backend when a `MediaAsset` is deleted.

#### 3. Authorization & Clinic Isolation ([`apps/media/permissions.py`](file:///c:/Users/Ali/Desktop/AESTHETIC_WAY_BACKEND/apps/media/permissions.py))
- **Patient Isolation:**
  - Patients can only upload and manage `patient_profile_image`.
  - Patients cannot upload any clinic-scoped media types or specify `clinic_id`.
  - Patients can delete only their own uploaded profile images.
- **Clinic Isolation:**
  - Clinic staff and admins can upload and manage media **only** for their assigned active clinic.
  - Cross-clinic access or upload attempts are rejected.
  - Clinic users cannot upload patient profile images.
  - Inactive / suspended clinic memberships are blocked.
- **Admin Override:**
  - Super admins can upload and delete any media type for any clinic or platform-wide content.

#### 4. Serializers & APIs ([`apps/media/serializers.py`](file:///c:/Users/Ali/Desktop/AESTHETIC_WAY_BACKEND/apps/media/serializers.py), [`apps/media/views.py`](file:///c:/Users/Ali/Desktop/AESTHETIC_WAY_BACKEND/apps/media/views.py), [`apps/media/urls.py`](file:///c:/Users/Ali/Desktop/AESTHETIC_WAY_BACKEND/apps/media/urls.py))
- **Upload Endpoint:** `POST /api/v1/media/upload/`
  - Multipart parser, validates file and permissions, returns HTTP 201 with public URL and dimensions.
- **Detail / Delete Endpoint:** `GET /api/v1/media/<uuid:pk>/`, `DELETE /api/v1/media/<uuid:pk>/`
  - Object-level permission check; deletion cleans up the storage backend and returns HTTP 204.
- **List Endpoint:** `GET /api/v1/media/`
  - Automatically scoped by user role (patient sees own images, clinic user sees clinic media, admin sees all).

---

## 2. Verification Results

### Unit & Security Test Suite
Created [`apps/media/tests/test_media_security.py`](file:///c:/Users/Ali/Desktop/AESTHETIC_WAY_BACKEND/apps/media/tests/test_media_security.py) covering 23 test scenarios:
- Valid JPEG, PNG, WebP uploads and dimension extraction.
- Blocked executable / dangerous extensions (`.exe`, `.sh`, `.bat`, `.php`, `.svg`).
- Blocked spoofed extension files (executable disguised as `.jpg`).
- Blocked oversized files (> 5MB) and zero-byte files.
- Patient upload restrictions & ownership deletion guards.
- Clinic staff permissions across all 7 clinic media types.
- Clinic cross-tenant isolation (Clinic A staff blocked from Clinic B).
- Inactive clinic membership denial.
- Super admin platform content upload and global deletion override.
- Storage backend cleanup upon asset deletion.
- PostgreSQL binary blob prevention (verified database column stores path string).

### Full Test Suite Run
```
============================ 109 passed in 52.59s =============================
```
- Total test cases: **109 passed** across the entire project (`accounts`, `admin_portal`, `analytics`, `home`, `leads`, `media`, `notifications`, `referrals`).
- Code linting: `ruff check apps/media` passed with zero errors.
