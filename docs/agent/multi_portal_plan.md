# 3EK LMS — Multi-Portal Architecture Plan

## The Vision

A single `/login` page that lets the user **select who they are first**, then authenticates them into a completely separate interface. No landing on the wrong dashboard. No shared menus.

---

## Current State (What Already Exists ✅)

| Component | Status |
|---|---|
| `StaffUser` model (session-only, no DB row) | ✅ Exists |
| Admin login → CRM (`/api/v1/crm/auth/verify`) | ✅ Exists |
| Admin dashboard → Workshop management | ✅ Exists |
| `Learner` model in `workshops/models.py` | ✅ Exists (needs password field) |
| `WorkshopRegistration` model | ✅ Exists |
| MS Graph email (invitation sending) | ✅ Done |
| TomSelect searchable dropdowns | ✅ Done |

---

## The Login Screen Redesign

### Single `/login` route — Role Selector First

Inspired by 3EK Pulse's design: premium dark, glassmorphism cards.

```
┌─────────────────────────────────────────────────┐
│                  3EK LMS                        │
│         "Who are you signing in as?"            │
│                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │  🏢      │ │  👔      │ │  🎓      │ │  📚    │ │
│  │ Admin    │ │ Client   │ │ Trainer  │ │ Learner│ │
│  └──────────┘ └──────────┘ └──────────┘ └─────────┘ │
│                                                 │
│  [Selected: Admin] → email + password form      │
└─────────────────────────────────────────────────┘
```

**UX Flow:** Click card → form slides in below → submit authenticates against the correct backend.

---

## Portal 1: Admin

> **Existing. Just needs routing fix.**

### Auth Flow
- **Password-based** → 3EK Pulse CRM API (`/api/v1/crm/auth/verify`)
- Role on CRM must be `admin` or `super_admin`
- Already implemented via `StaffUser` session model

### Interface
- Already built (workshop CRUD, trainer management, document upload, email blasts)
- **Redirect after login:** `/workshops` (not dashboard)

### Missing → To Address
| Feature | Priority |
|---|---|
| Dashboard (summary cards: total workshops, registrations, revenue, upcoming) | High |
| Bulk actions on registration list | Medium |
| Email log history viewer | Medium |

---

## Portal 2: Client

> **New — moderate build**

### Who is a Client?
A corporate entity (company) that books 3EK workshops — either customised in-house batches or enrolled group seats.

### Auth Flow
- **OTP-based (passwordless)** — no password stored in CRM or LMS
- Flow:
  1. Client enters their **email address** on the login screen
  2. LMS calls CRM API to **verify the email exists** as an active Contact (`/api/v1/crm/contacts/lookup?email=`)
  3. If found → generate a 6-digit OTP → store in **Redis** (TTL: 10 minutes) → send via **MS Graph email**
  4. Client enters OTP → Redis validates → `ClientUser` session created
- On success → `ClientUser` session object (similar to `StaffUser`)

> [!NOTE]
> The CRM only needs a **read-only lookup endpoint** (`/api/v1/crm/contacts/lookup`), not a verify/password endpoint. No CRM changes to auth logic.

### What They See
1. **My Company's Bookings** — list of workshops booked for their organisation
2. **Participant List** — view/download who from their team is enrolled
3. **Materials** — access documents uploaded by the admin for their workshop
4. **Invoice/Payment Status** — view payment history, download receipts
5. **Feedback Dashboard** — post-workshop NPS and attendance scores (read-only)

### Key Constraint
- Client only sees registrations where `WorkshopRegistration.company` matches their CRM company name, OR where `Workshop.crm_client_id` matches their CRM client ID

---

## Portal 3: Trainer

> **New — lightweight build**

### Who is a Trainer?
A subject matter expert or facilitator who delivers workshops. Already in CRM as a `Trainer` record.

### Auth Flow
- **OTP-based (passwordless)** — same pattern as Client portal
- Flow:
  1. Trainer enters their **email address**
  2. LMS calls CRM API to **verify the email exists** as an active Trainer (`/api/v1/crm/trainers/lookup?email=`)
  3. If found → 6-digit OTP → stored in **Redis** (TTL: 10 min) → sent via **MS Graph email**
  4. Trainer enters OTP → Redis validates → `TrainerUser` session created with their `crm_trainer_id`

> [!NOTE]
> Again, CRM only needs a **read-only lookup endpoint** (`/api/v1/crm/trainers/lookup`). No password logic.

### What They See
1. **My Upcoming Workshops** — only workshops where they are assigned as a trainer (`WorkshopTrainer.crm_trainer_id`)
2. **Participant List** — names, emails and company of enrolled learners for their specific workshop
3. **Session Management** — mark attendance (`WorkshopRegistration.attended`)
4. **Materials** — view/upload workshop materials for their assigned sessions
5. **My Profile** — view their trainer profile pulled from CRM

### Key Constraint
- All queries scoped by `crm_trainer_id` — they cannot see other workshops

---

## Portal 4: Learner

> **New — most substantial build**

### Who is a Learner?
An individual who registers for and attends workshops. Already has a `Learner` model in the LMS DB.

### Auth Flow
- **OTP-based (passwordless)** — same mechanism, different data source
- Flow:
  1. Learner enters **email address**
  2. LMS checks its **own `Learner` table** (no CRM call needed)
  3. If found → 6-digit OTP → stored in **Redis** (TTL: 10 min) → sent via **MS Graph email**
  4. Learner enters OTP → Redis validates → `LearnerUser` session created
- If email **not found**: show option to self-register (create a `Learner` row)
- On success → `LearnerUser` session backed by actual `Learner` DB row

### What They See
1. **My Learning Dashboard** — enrolled workshops, progress, upcoming sessions
2. **Course Materials** — documents for workshops they're registered in
3. **Session Recordings** — video playback (using existing `WorkshopVideoProgress` tracking)
4. **Certificates** — download issued certificates (using existing `Certificate` model)
5. **Profile** — update name, phone, company
6. **Workshop Discovery** — browse and self-register for upcoming public workshops (`is_public=True`)

---

## Architecture Map

```
app/
├── auth/
│   ├── routes.py         ← Add role-specific login handlers
│   ├── models.py         ← Add ClientUser, TrainerUser, LearnerUser session classes
│   └── templates/
│       └── login.html    ← Full redesign: role-selector + animated form
│
├── admin/                ← Rename from current workshops (or keep as-is)
│   └── (existing)
│
├── client/               ← NEW Blueprint
│   ├── __init__.py
│   ├── routes.py
│   └── templates/
│
├── trainer/              ← NEW Blueprint
│   ├── __init__.py
│   ├── routes.py
│   └── templates/
│
└── learner/              ← NEW Blueprint
    ├── __init__.py
    ├── routes.py
    └── templates/
```

---

## Shared Infrastructure Needed

| Component | Used By | Notes |
|---|---|---|
| `login_required` decorator per portal | All 4 | Flask-Login supports multiple user loaders — one per user type |
| **OTP Service** (Redis + MS Graph) | Trainer, Client, Learner | Redis in `.env` ✅; MS Graph email working ✅ — **shared service, 1 implementation** |
| `crm_client.lookup_contact(email)` | Client portal | Read-only CRM lookup only — no password logic |
| `crm_client.lookup_trainer(email)` | Trainer portal | Read-only CRM lookup only — no password logic |
| Role-guard decorators | All | `@client_required`, `@trainer_required`, `@learner_required` |
| Separate base templates | All | `base_admin.html`, `base_client.html`, `base_trainer.html`, `base_learner.html` |

---

## Build Sequence (Recommended Order)

### Phase A: Login Screen Redesign
- Redesign `/login` with the 4-card role selector
- Wire Admin card to existing CRM auth (no change in backend)
- Other 3 cards show "Coming Soon" state initially

### Phase B: Trainer Portal
- Simplest to build (read-only, scoped by `crm_trainer_id`)
- Add `verify_trainer` to CRM client
- Create `trainer/` blueprint with 3 views: My Workshops, Participants, Materials

### Phase C: Learner Portal
- Build OTP flow using Redis (already configured) + MS Graph (already working)
- Wire `Learner` model to login session
- Build dashboard, materials, recordings, certificates views

### Phase D: Client Portal
- Requires CRM to expose a contact verification endpoint
- Build company-scoped views for bookings and participants

---

## What the CRM Needs to Provide (`localhost:8013`)

| Endpoint | Purpose | Priority |
|---|---|---|
| `POST /api/v1/crm/auth/verify` | Admin login — **exists** ✅ | Done |
| `GET /api/v1/crm/trainers/lookup?email=` | Check if trainer email exists | Phase B |
| `GET /api/v1/crm/contacts/lookup?email=` | Check if client/contact email exists | Phase D |

> [!IMPORTANT]
> The CRM only needs **two simple read-only lookup endpoints** — no password fields, no auth logic. The LMS handles all OTP generation/validation itself using Redis + MS Graph. This is a minimal ask of the CRM team.

> [!NOTE]
> The `Learner` table is fully owned by the LMS — no CRM call needed for learner login at all.

---

## Summary of What Gets Built

| Portal | Auth Source | DB Owner | Effort |
|---|---|---|---|
| **Admin** | 3EK Pulse CRM | CRM (session only in LMS) | Minimal (redirect fix) |
| **Trainer** | CRM via API | CRM | Low |
| **Client** | CRM via API | CRM | Medium |
| **Learner** | LMS (OTP) | LMS `Learner` table | High |
