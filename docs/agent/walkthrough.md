# Client Portal: Self-Service Hub — Walkthrough

## What Was Built

A complete transformation of the Client/Corporate portal into a **6-page self-service hub** that gives clients a full view of their relationship with 3EK — from training history to invoices to open requirements.

---

## Pages Built

| Page | Route | Source |
|---|---|---|
| Dashboard | `/client/` | CRM + LMS |
| My Programs | `/client/programs` | CRM Engagements |
| Program Detail | `/client/programs/<id>` | CRM Engagement + Invoices + Docs |
| Open Requests | `/client/requests` | CRM Inquiries |
| Discover | `/client/workshops` | LMS public workshops |
| Company Profile | `/client/profile` | CRM Client + Contact + User |

---

## Backend Changes

### 3EK-Pulse (`internal_crm_routes.py`) — 5 new endpoints
- `GET /programs?client_id=X` — all engagements for a client (safe fields, no financials)
- `GET /programs/<id>` — single engagement + invoices + client-safe documents
- `GET /requests?client_id=X` — open/active training inquiries
- `GET /clients/<id>/account-manager` — Account Manager name + email + mobile
- `POST /contacts/verify` — real Werkzeug password check for CRM Contact model

### LMS `crm_client/client.py` — 5 new wrapper functions
`get_programs_for_client()`, `get_program_detail()`, `get_open_requests()`, `get_account_manager()`, `verify_contact_password()`

### LMS `auth/routes.py` — Upgraded Client Login
Now tries CRM Contact's real `check_password()` first. Falls back to master password + email lookup for contacts without passwords set in Pulse.

---

## Verification (Browser Test — Hexaware: `anil.k@hexaware.com`)

![Dashboard](/Users/shuaib/.gemini/antigravity/brain/7f0111e2-ed0b-4745-a535-d94c6fc8939e/client_dashboard_verify_order_1773105901633.png)
*Dashboard (Clean Layout): Open requests now prioritized at the top over active engagements*

### Git & Documentation
- **Pulse CRM Patch**: Committed to `3EK-Pulse` (`main`).
- **LMS Project**: All new portals and features committed to `3ek-lms`.
- **Organized Docs**: Created a new [docs/agent](file:///Users/shuaib/Documents/Projects/3ek-lms/docs/agent) folder containing all the design implementation plans, tasks, and verification walkthroughs for permanent record.
- **Push Status**: `3EK-Pulse` pushed successfully. `3ek-lms` is ready to push once a remote URL is configured.

![Trainer Dashboard Imtiyaz](/Users/shuaib/.gemini/antigravity/brain/7f0111e2-ed0b-4745-a535-d94c6fc8939e/trainer_dashboard_full_1773111612673.png)
*Final Verification: Imtiyaz Hirani's dashboard showing assigned workshops with the new Excel-style layout.*

![Programs](/Users/shuaib/.gemini/antigravity/brain/7f0111e2-ed0b-4745-a535-d94c6fc8939e/programs_table_layout_full_1773104933023.png)
*My Programs (Excel-Style): High-density data table consolidating both active and past training engagements for administrative ease*

## Verification (Browser Test — Trainer Portal)

![Trainer Dashboard](/Users/shuaib/.gemini/antigravity/brain/7f0111e2-ed0b-4745-a535-d94c6fc8939e/trainer_dashboard_full_page_1773109434266.png)
*Trainer Dashboard (Excel-Style): "Assigned Workshops" and "Past Engagements" now use high-density borders and exact match layout with the corporate client portal.*

![Requests](/Users/shuaib/.gemini/antigravity/brain/7f0111e2-ed0b-4745-a535-d94c6fc8939e/client_requests_1773103041539.png)
*Open Requests: Training pipeline with stage tracker (Under Discussion → Scheduled)*

![Discover](/Users/shuaib/.gemini/antigravity/brain/7f0111e2-ed0b-4745-a535-d94c6fc8939e/client_workshops_1773103061163.png)
*Discover: Public LMS workshops with Share with Team button*

---

## Key Design Decisions

- **No financial data exposed**: Invoices show amount, balance, and status — not trainer costs or margins
- **Pipeline stage labels**: Inquiry stages translated from internal CRM status to client-friendly labels (`Under Discussion`, `Trainer Matching`, `Scheduled`)
- **Document filtering**: Only client-safe document types shown (`Course Outline`, `Attendance Sheet`, `Client PO`, `Feedback Report`)
- **Account Manager card**: Shows AM name + email + mobile with pre-filled email button throughout dashboard and profile
