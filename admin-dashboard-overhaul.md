# Admin Enterprise Navigation & Dashboard Overhaul

## Overview
The user correctly identified that trying to manage all data (trainers, participants, revenue) from a single "Workshops" view will not scale as the platform grows to include Assessments, Labs, and thousands of historical records from Pulse.

We are abandoning the "Asymmetric Drawer" concept in favor of a true **Enterprise Routing & Metrics Dashboard Strategy**, applying the `frontend-specialist` principles for data-dense, scalable layouts.

## Objective
1. Transform the "Dashboard" home route (`/workshops/`) into a dedicated **Metrics & Actions Dashboard**.
2. Expand the global Sidebar (`layouts/base.html`) to include dedicated top-level domains: Workshops, Training Management, Participants, Labs, and Reports.
3. Ensure the UI remains sharp, non-chaotic, and avoids generic "SaaS template" layouts by utilizing structured data grids and high-contrast typography.

---

## Task Breakdown

### Task 1: Re-architect the Global Sidebar (`layouts/base.html`)
**Agent:** `frontend-specialist`
- **Action:** Update the sidebar navigation items.
- **New Structure:**
    - **Dashboard** (Metrics, KPIs, Alerts)
    - **Workshops** (The current list view, focused only on course creation/status)
    - **Participants** (Global roster, Pulse history, Assessment scores)
    - **Training Management** (Trainer schedules, resource allocation)
    - **Labs & Assets** (Future-proofing for technical environments)

### Task 2: Create the Dedicated Metrics Dashboard (`dashboard.html`)
**Agent:** `frontend-specialist` & `backend-specialist`
- **Backend:** Create a new `/` or `/dashboard` route that aggregates high-level data: Total revenue, active learners, upcoming sessions under capacity, and a feed of recent registrations.
- **Frontend Design:** 
    - **Anti-Safe Harbor Design:** Do not use predictable 4-column Bento grids for metrics.
    - **Topological Choice:** Use an aggressive typographic hierarchy. Make primary KPIs massive (e.g., 80px font) and push secondary tables to a distinct, dark-themed lower half.
    - **Geometry:** 0px to 2px border radius. Sharp, technical feel.

### Task 3: Dedicated Domain Views (Workshops, Participants, Trainers)
**Agent:** `frontend-specialist`
- **Workshops View:** Strip the current `list.html` of excessive details (like seat progress bars on every card if it becomes overwhelming). Transition to a dense data-table for scale, over big "Cards".
- **Participants View:** Create the scaffolding for the global participant table. (To be hydrated later with Pulse data).

---

## Phased Approach for Immediate Execution

To avoid "chaos" and overwhelming the codebase, we will take this sprint step-by-step:

**Immediate Next Steps (Phase 1):**
1. Modify `base.html` to establish the new navigational skeleton (putting the new menu items in place, even if they point to "Coming Soon" placeholders for now).
2. Build the new **Metrics Dashboard** as the landing page, displaying real aggregate numbers from the database (Active workshops, total registrations, revenue).
3. Move the existing Workshop List to a dedicated `/workshops/manage` route.

Are we aligned with this structural pivot toward an Enterprise Navigation model over the sliding drawer concept?
