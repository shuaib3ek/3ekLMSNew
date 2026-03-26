# LMS Participant Full Lifecycle Plan — Revised

## The Big Picture

Participants (added to a CRM program via CSV or manually) need to log in and see their dashboards. The good news: **the Learner system already handles this**.

### How the Learner auth works today:
- Learner logs in with **email + shared password** (`3ek2026`) at `/auth/login?role=learner`
- The system checks if that email exists in the `learners` table
- If yes → logs them in and redirects to `/learner/dashboard`

### Our strategy: **Provision participants as Learners**
Instead of building a new login system, we register each `ProgramParticipant` as a `Learner` row when they are added to a program. This means:
- They log in via the **existing** `/auth/login` page (role = learner)
- They land on the **existing** learner dashboard — which we **extend** to show their Labs and Assessments
- No new auth code. No new login page.

---

## Current State (What exists)

| | Status |
|---|---|
| `Learner` model with `email`, `password_hash`, `username` | ✅ Exists |
| Learner login (password + OTP both work) | ✅ Exists |
| Learner Dashboard (`/learner/`) | ✅ Exists (shows Workshops only) |
| `ProgramParticipant` model | ✅ Exists |
| Assessments assigned to participants | ✅ Exists |
| Labs assigned to participants | ✅ Exists |
| Link between `ProgramParticipant` and `Learner` | ❌ Missing |
| Learner Dashboard showing Labs + Assessments | ❌ Missing |

---

## What Needs to Be Built

### Phase 1 — Auto-Provision Learner Accounts (Backend)

**When:** Admin adds a participant (manually or via CSV upload)  
**What:** Automatically create a `Learner` row for that participant email if one doesn't already exist  
**Files to change:**
- `app/training_management/routes.py` — `add_participant()` and `upload_participants()` — add Learner creation after saving the participant

**Password Strategy:**  
Default password = `3eks@learn` (more secure than `user@123`, but still simple enough to communicate)  
An admin can also trigger OTP-based login instead.

**What this gives us:**  
Participant can now log in at `/auth/login?role=learner` with their email + `3eks@learn`

---

### Phase 2 — Cross-Link Participant ↔ Learner (Data)

**What:** Add `learner_id` column to `ProgramParticipant` so we can connect the dots  
**Files to change:**
- `app/training_management/models.py` — add `learner_id = db.Column(db.Integer, db.ForeignKey('learners.id'), nullable=True)`
- Create and run a DB migration

---

### Phase 3 — Learner Dashboard: Show Labs & Assessments (Frontend)

**What:** Extend the learner dashboard to show their assigned Labs and Assessments from active programs  
**Files to change:**
- `app/learner/routes.py` — `dashboard()` — add query to fetch `ProgramParticipant` by email → then load their `AssessmentAssignment` and `LabAssignment`
- `app/templates/learner/dashboard.html` — add two new cards: "My Assessments" and "My Virtual Labs"

---

### Phase 4 — Participant Actions (Frontend + Backend)

#### Assessment Actions
- View assessment (link/PDF opens in new tab)
- "Mark as Submitted" button → `POST /learner/assessment/<id>/submit`
- Admin sees status in Assessments menu change to `submitted`

#### Lab Actions
- "Launch Lab" button → opens `lab_url` in new tab
- "Mark Complete" button → `POST /learner/lab/<id>/complete`
- Admin sees status in Labs menu change to `completed`

**New routes needed in `app/learner/routes.py`:**
- `POST /assessment/<assignment_id>/submit`
- `POST /lab/<assignment_id>/complete`

---

### Phase 5 — Admin: Send Welcome Email (Optional but Recommended)

**What:** "Send Welcome" button on Program Detail page → emails each participant their login URL and default password  
**Files to change:**
- `app/training_management/routes.py` — new route `send_invites()`
- `app/templates/training_management/detail.html` — add "Send Invites" button
- `app/services/participant_invite_service.py` [NEW] — email template + send logic using existing `ms_graph_service.py`

---

## Full Flow After These Changes

```
[CSV Upload / Manual Add]
  ↓
ProgramParticipant created + Learner account auto-created (email + default password)
  ↓
Admin clicks "Send Invites" → Each participant gets email:
  "Login at lms.3ek.in with {email} / 3eks@learn"
  ↓
Participant logs in → Redirected to Learner Dashboard
  ↓
Dashboard shows: My Workshops | My Assessments | My Labs
  ↓
Participant launches lab URL / downloads and submits assessment
  ↓
Admin sees status change in Assessments/Labs menu
  ↓
Admin grades → (Future) Certificate issued
```

---

## Priority Order

| # | Task | Files | Priority | Effort |
|---|---|---|---|---|
| 1 | Fix Upload CSV + Add Participant Modals | `detail.html`, `style.css` | 🔴 High | S |
| 2 | Auto-create Learner on participant add/upload | `training_management/routes.py` | 🔴 High | S |
| 3 | Add `learner_id` FK to `ProgramParticipant` + Migration | `models.py`, DB | 🔴 High | S |
| 4 | Extend Learner Dashboard with Labs + Assessments | `learner/routes.py`, `dashboard.html` | 🔴 High | M |
| 5 | Participant submit/complete actions | `learner/routes.py` | 🟡 Medium | M |
| 6 | Send Welcome Email to participants | `routes.py`, `invite_service.py` | 🟡 Medium | M |

> S = Small (< 2 hrs), M = Medium (half day)
