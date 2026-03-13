# 3EK Enterprise Admin Portal Architecture Plan

## 1. Vision & Problem Statement
As the 3EK LMS scales, the current administrative view (where everything orbits around the "Workshop List") will become chaotic and unmanageable. To scale into a true Learning Experience Platform (LXP), we must transition from a "Workshop-centric" model to a **Domain-centric Enterprise Architecture**.

In this new paradigm, the main **Dashboard is exclusively for metrics and high-level KPIs**, while operational tasks are split into dedicated, discrete menu items: Workshops, Training Sessions, Participants, and Labs.

---

## 2. Core Architectural Philosophy
*   **Anti-Chaos (Miller's Law):** We will not cram rosters, trainers, and revenue into one screen. Each domain gets its own dedicated space.
*   **Data Density (Typography over Boxes):** We will avoid the "SaaS Bento Box" trap. Instead of using massive rounded cards to display 3 numbers, we will use dense, high-contrast data tables, aggressive typographic hierarchy, and sharp edges (0-2px border radius).
*   **No Purple Ban:** The interface will utilize a technical, premium palette (e.g., Deep Slate, Acid Green for positive metrics, stark white/black contrast) rather than generic soft templates.

---

## 3. The New Global Navigation (Sidebar Structure)

The left-hand sidebar will be reorganized to represent these specific administrative pillars:

### 📊 1. Command Center (Dashboard)
**Function:** A pure metrics, analytics, and alerts screen. Overview of active enrollments and revenue.

### 📅 2. Workshops (Current LMS Core)
**Function:** Management of active open-enrollment training.
**Key Elements:**
*   Creation of curricula, pricing, scheduling, and direct management of live workshop sessions within the LMS.

### 👨‍🏫 3. Training Management (Historical Pulse Data)
**Function:** A read-only historical archive of B2B and past training programs.
**Key Elements:**
*   **Data Source:** Pulled dynamically from the existing `3ek-pulse` system.
*   **UI Behavior:** Displays a read-only list of ongoing and past programs. Clicking on a specific training program opens a link back to the native `3ek-pulse` dashboard for deep management. 
*   *Future Note:* Significant UI/UX enhancements will be required to eventually migrate this management natively into the LMS.

### 👥 4. Learners (Workshop Participants Only)
**Function:** The active database of learners currently engaged in LMS Workshops.
**Key Elements:**
*   *Constraint:* For now, this roster ONLY tracks participants attending active "Workshops" created in the LMS, not the historical training data from Pulse.

### 🧪 5. Assessments & 💻 6. Labs (Future Scaffolding)
*   **Status:** *Dead Links*
*   **Function:** Placeholder UI elements in the sidebar to visualize the future scope of the LXP. Clicking them currently results in a "Coming Soon" or disabled state.

---

## 4. Expert UI/UX Interface Recommendations (LMS Specific)

As an LMS grows, the "Grid of Cards" (the current `list.html`) fundamentally breaks. The hallmark of a Tier-1 Enterprise LXP is its ability to visualize complex learner cohorts without overwhelming the administrator. 

To achieve this, we will implement the **"Air Traffic Control" (ATC) Layout Pattern**, strictly adhering to our anti-cliché design rules:

### 📐 The ATC Layout Strategy
1.  **Macro-Layout (Extreme Asymmetry - 80/20 Split):** 
    *   **The Left Rail (20%):** A persistent, pitch-black (`#020617` Slate 950) navigation column. High contrast, low distraction.
    *   **The Data Theater (80%):** A stark white main content area. We will not use light gray backgrounds with drop-shadowed white boxes. Everything sits flat on the same layer to eliminate visual clutter.
2.  **Geometry:** *Brutalist & Technical.* Absolutely **0px border-radius** on all primary structural elements (containers, tables). We want this to feel like a high-performance database interface, not a consumer social app.
3.  **Typography over Charts:** Instead of utilizing circular gauges or pie charts that consume massive screen real estate, we rely on **Typographic Brutalism**. Key metrics (e.g., "75% Completion Rate") are rendered in massive, bold typography (e.g., 64px `Inter` Heavy), overshadowing the secondary text.
4.  **The "Pulse/Health" Paradigm:** Instead of just listing "Workshops," the dashboard will prioritize **Anomalies and Health**. 
    *   *Green (Acid Green `#a3e635`):* Workshops filling exactly to capacity, High assessment scores.
    *   *Orange (Signal Orange `#ea580c`):* "At Risk" cohorts (e.g., sessions next week with <30% fill rate). 
    *   *Red (Crimson `#e11d48`):* Conflicts (Double booked trainers).

### ⚡ Navigation Flow (Zero Page-Load Illusion)
*   **The Drawer Pattern (instead of deep linking):** When you click on a Specific Learner or a specific Workshop session, the browser does not reload. A massive, data-dense drawer slides out from the right (occupying 70vw). 
*   **Why?** This prevents "Context Loss". An admin can check a learner's past Pulse history, close the drawer, and instantly be back at the exact row of the master table they were looking at.

### 🚫 Banned Clichés
*   **No "Purple/Neon" Accents:** No "AI glassmorphism." We use solid colors only.
*   **No Bento Grids:** Do not try to fit complex training rosters into a 3x3 grid of cute squares. We embrace the **Stark Data Table** with sticky headers and ultra-condensed rows for maximum information density.

---

## 5. Phased Execution Strategy (How we build this)

This is a massive overhaul. It must be built incrementally to ensure the platform remains stable.

*   **Phase 1: The Metrics Dashboard & Navigation Skeleton (Start Here)**
    *   Update `base.html` to reflect the new sidebar (Workshops, Training Management, Learners, Assessments, Labs).
    *   Build the pure metrics `/dashboard` route as the new default landing page.
    *   Map the existing workshop list functionality strictly to the **Workshops** menu.
*   **Phase 2: Training Management (Pulse Integration)**
    *   Build the read-only list view that fetches ongoing/past programs from the Pulse API.
    *   Implement redirect links so clicking a program opens the respective Pulse URL.
*   **Phase 3: The Dedicated Learner Roster**
    *   Extract the learner component out of the workshop details page and into a global (but workshop-exclusive) `Learners` table.
*   **Phase 4: Labs & Assessments**
    *   Build the infrastructure for technical labs and quizzes.

---
*No code changes have been made. This document serves as the architectural blueprint for the enterprise redesign.*
