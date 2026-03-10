# Client Portal: Full Self-Service Corporate Hub (Revised)

Deep audit of 3EK-Pulse reveals far richer data than initially planned. This is the full build-out plan.

---

## What the CRM Has (That Clients Want)

| CRM Model | Client-Safe Fields | Value to Client |
|---|---|---|
| **Engagement** | topic, dates, status, trainer_name, duration, training_type, participants | Full program history |
| **EngagementInvoice** | invoice_number, date, amount (gross), balance, status, zoho PDF URL | Invoice tracker |
| **EngagementDocument** | filename, file_type (Client PO, Course Outline, Attendance Sheet) | Secure document vault |
| **Inquiry** | topic, status (open/won/lost), urgency, participants_count, requested_start_date | Open training requests |
| **Client** | company_name, website, industry, billing_address, gst_number, account_manager | Company profile |
| **User (Account Manager)** | display_name, email, mobile | Their direct 3EK contact |
| **Contact** | password_hash (native login!), job_title, department | Secure portal login |

> [!IMPORTANT]
> The `Contact` model already has `password_hash`, `lms_access_granted`, and `lms_setup_token` fields — **the CRM is designed for client portal login**. We should use Werkzeug's `check_password` on the CRM's own hash for login, removing the need for master passwords.

---

## Portal Pages (6 Sections)

### Page 1: Dashboard (Home)
**Source: CRM + LMS**

- **Summary Stats bar**: Total programs delivered, Total participants trained, Years with 3EK
- **Active Programs widget**: Upcoming/in-progress engagements from CRM (card per engagement)
- **Open Requests tracker**: Any Inquiries with status=`open` — shows topic, urgency pill, requested date
- **Quick Actions**: "Explore Workshops", "New Training Request" (→ email), "Contact Account Manager"

---

### Page 2: My Programs (`/programs`)
**Source: CRM Engagements**

Two tabs: **Active** and **Past**

Each card shows:
- Topic, Training Type badge (VILT / Classroom / Hybrid)
- Trainer Name
- Date range + Duration
- Status pill (SCHEDULED / IN PROGRESS / COMPLETED / CANCELLED)
- Link to Program Detail →

---

### Page 3: Program Detail (`/programs/<eng_id>`)
**Source: CRM Engagement + EngagementInvoice + EngagementDocument**

Sections:
1. **Header**: Topic + dates + status timeline (Scheduled → In Progress → Completed)
2. **Trainer Card**: Name (no contact details shared, just name)
3. **Invoice Tracker** (client-safe fields only):
   - Invoice Number, Date, Gross Amount, Balance Due, Status
   - Link to PDF if `zoho_client_invoice_url` is set
4. **Documents Vault**: Attendance Sheet, Course Outline, Client PO copies
5. **LMS Link**: If linked to an LMS Workshop → "View Enrollment Roster →"

> [!NOTE]
> We **never expose** `final_trainer_cost`, `gross_margin`, or any internal financial metrics. Only client-side invoice data is shown.

---

### Page 4: Open Requirements (`/requests`)
**Source: CRM Inquiries with status=open**

A tracker view showing all pending training requests the company has submitted:

| Topic | Requested | Participants | Urgency | Status |
|---|---|---|---|---|
| Gen AI for Managers | 15 Mar 2026 | 30 | Urgent | Under Discussion |
| Python Bootcamp | Flexible | 12 | Medium | Trainer Matching |

> [!TIP]
> This is a huge value-add — clients always ask "what's the status of that requirement we sent?" Now they can self-serve.

---

### Page 5: Discover Workshops (`/workshops`)
**Source: LMS — public workshops**

A browsable grid of upcoming public workshops. Each card:
- Title, Date, Mode, Seats Available
- **"Share with Team"** button → copies the workshop registration URL to clipboard
- **"Register Now"** → opens registration page in new tab

---

### Page 6: My Profile + Account Manager (`/profile`)
**Source: CRM Client + Contact + Account Manager User**

- Company card: Name, Industry, GST, Website, Billing Address
- Your contact profile: Name, Title, Department, Email
- **Account Manager card**: Name, Email, Mobile — their dedicated 3EK contact
- "Need a new program?" → pre-filled email to account manager

---

## Implementation: Pulse API Additions

#### [MODIFY] [internal_crm_routes.py](file:///Users/shuaib/Documents/Projects/3EK-Pulse/app/api/internal_crm_routes.py)

Add these 5 endpoints:

| Endpoint | Returns |
|---|---|
| `GET /programs?client_id=X` | All Engagements for client (safe fields only) |
| `GET /programs?trainer_id=X` | All Engagements for trainer (safe fields only) |
| `GET /programs/<id>` | Single Engagement + its Invoices + Documents |
| `GET /requests?client_id=X` | All open Inquiries for client |
| `GET /clients/<id>/account-manager` | Account Manager name + email + mobile |
| `GET /contacts/login` (POST) | Verify contact email + password using `check_password()` |

---

## Implementation: LMS Changes

### CRM Wrapper Functions
#### [MODIFY] [client.py](file:///Users/shuaib/Documents/Projects/3ek-lms/app/crm_client/client.py)
Add: `get_programs_for_client()`, `get_programs_for_trainer()`, `get_program_detail()`, `get_open_requests()`, `get_account_manager()`

### Routes
#### [MODIFY] [routes.py](file:///Users/shuaib/Documents/Projects/3ek-lms/app/client/routes.py)
Add routes for `/programs`, `/programs/<id>`, `/requests`, `/workshops`

### Auth — Real Password Login via CRM Contact
#### [MODIFY] [routes.py](file:///Users/shuaib/Documents/Projects/3ek-lms/app/auth/routes.py)

Replace master password hack for clients with a proper `POST /api/v1/crm/contacts/login` call that uses `check_password()` on the CRM Contact's own `password_hash`. This requires contacts to have passwords set in Pulse, otherwise falls back to master password.

### New Templates
#### [NEW] [program_detail.html](file:///Users/shuaib/Documents/Projects/3ek-lms/app/templates/client/program_detail.html)
#### [NEW] [requests.html](file:///Users/shuaib/Documents/Projects/3ek-lms/app/templates/client/requests.html)
#### [NEW] [discover.html](file:///Users/shuaib/Documents/Projects/3ek-lms/app/templates/client/discover.html)
#### [MODIFY] [dashboard.html](file:///Users/shuaib/Documents/Projects/3ek-lms/app/templates/client/dashboard.html)
#### [MODIFY] [profile.html](file:///Users/shuaib/Documents/Projects/3ek-lms/app/templates/client/profile.html)

---

## Verification Plan

1. `curl /api/v1/crm/programs?client_id=229` returns Hexaware engagements
2. `curl /api/v1/crm/requests?client_id=229` returns open inquiries
3. Login as `anil.k@hexaware.com` → see Dashboard with programs + open requests
4. Click a program → see Program Detail with dates, trainer, invoice row
5. Click "Discover Workshops" → see upcoming public LMS workshops with share links
6. View Profile → see Company info + Account Manager card

---

## Build Order

1. ✅ Pulse API endpoints (no LMS changes, just CRM additions)
2. ✅ CRM wrapper functions in LMS
3. ✅ Route additions
4. ✅ 3 new templates + 2 modified templates
