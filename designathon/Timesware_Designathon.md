# Timesware — Tech-Triathlon 2026 Designathon

## Waypoint Group Delivery Planning System

**Team:** Timesware — MFM Ayyash and MKH Hafees
**Phase:** Designathon (Day 5 deadline)

**Links**

* Prototype: https://hafees14.github.io/timesware-tech-triathlon-2026/
* Figma: https://www.figma.com/design/j3b3g8u5DfCEwmVs99uavf/Tech_Triathlon_2026_Timesware
* Demo video (unlisted): https://youtu.be/R66atItt5bE
* Repository: https://github.com/Hafees14/timesware-tech-triathlon-2026

---

## 1. User Personas

### Dispatcher — Nadeeka

* **Where she works**: Peliyagoda planning office, large screen, stable connectivity.
* **What she does today**: Builds tomorrow's delivery plan in a spreadsheet after the 4 PM order cutoff, using memory of which outlets are awkward, which vehicles are in the shop, and which brand is fighting for capacity that day.
* **Pressure point**: Demand regularly exceeds fleet capacity. She has to decide who gets served and who gets deferred, often under time pressure, and she has no clean record of *why* she deferred something — so the same outlet can get skipped two days running by accident.
* **What she needs from the system**: A single queue of confirmed orders, a way to see capacity vs demand at a glance, an allocation view she can trust that respects hard constraints, live visibility into what's happening on the road after vehicles leave, and a deferral log she can point to when a store manager complains.

### Loader — Sampath

* **Where he works**: Peliyagoda or Kandy warehouse dock, shared tablet or terminal, noisy and physical environment.
* **What he does today**: Works off a printed loading list. If the dispatcher changes the plan after printing, he's the last to know.
* **Pressure point**: Loading in the wrong order means the driver has to dig through the truck at every stop. Missing or damaged stock discovered only after the truck leaves is a bigger problem than one caught at the dock.
* **What he needs from the system**: A live, always-current stop sequence per vehicle/trip so he loads last-stop-first, and a fast way to flag a shortfall or damaged item *before* the vehicle leaves — one that actually reaches the dispatcher, not just a note to himself.

### Driver — Ruwan

* **Where he works**: On the road, personal phone, one hand often not free, connectivity that drops in hill country and the Kandy corridor.
* **What he does today**: Paper run sheet, phone calls for anything that changes.
* **Pressure point**: No way to prove a delivery happened or record a problem without calling someone. When he's out of coverage, work just stops being recorded.
* **What he needs from the system**: A simple, glanceable stop list; one-tap outcome recording (delivered / attempted / issue) with proof of delivery; the ability to keep working with zero connectivity and have it sync later without drama; interactions designed for use while safely stopped, not while driving.

### Store Manager — Fathima

* **Where she works**: Outlet counter, desktop or phone, in between customers.
* **What she does today**: Places orders by phone or message with no confirmation they were received, let alone scheduled.
* **Pressure point**: No idea when (or if) a delivery is coming, so she can't staff the receiving dock, and no clean way to report that half an order didn't show up.
* **What she needs from the system**: Confirmation the order was captured before the cutoff; an expected arrival time; a clear, early notice if her order is deferred (not a surprise at 7:55 AM); a simple way to confirm what actually arrived and flag discrepancies.

---

## 2. Screen Flows by Role, with Rationale

Each screen below includes: user goal and context, why it's arranged that way, how it supports the workflow and constraints from the Challenge Booklet, and what happens next.

### 2.1 Store Manager

**Screen 1 — Place Order**

* *Goal/context*: Fathima needs to get an order in before the 4 PM cutoff, with fields that match her brand (Fresh orders need a chilled/ambient split; Style and Tech don't).
* *Arrangement*: Brand-aware form, cutoff countdown shown prominently at the top so she always knows whether she'll make today's run before she finishes filling it in.
* *Workflow/constraints*: Directly implements "capture and confirm the order before the cutoff" from the booklet's workflow table, and reflects that order timing differs by brand (Fresh daily, Style weekly, Tech as-needed).
* *Next*: Submitting moves her to the Order Confirmation screen.

**Screen 2 — Order Confirmation**

* *Goal/context*: Today she gets no confirmation her order was received at all — this screen exists specifically to close that gap.
* *Arrangement*: An explicit "received" state, shown distinctly from any later "scheduled" state, so the two are never conflated.
* *Workflow/constraints*: Addresses the booklet's stated problem that store managers place orders "without confirmation that they received or scheduled them."
* *Next*: She waits; the screen updates automatically once the dispatcher's allocation runs (Screen 3), or shows a deferral notice (Screen 4) if her order isn't served.

**Screen 3 — Delivery Status / Expected Arrival**

* *Goal/context*: Once the dispatcher has planned the day, Fathima needs an expected arrival time so she can staff the receiving dock.
* *Arrangement*: A single, simple status line (e.g. "Arriving ~6:42 AM") rather than a full route map — she doesn't need dispatcher-level detail, just what she needs to act on.
* *Workflow/constraints*: Matches the booklet's stated need: "an expected arrival time to schedule staff to receive goods."
* *Next*: Updates as the driver progresses; transitions to Confirm Receipt (Screen 5) once the driver marks the stop delivered.

**Screen 4 — Deferral Notice**

* *Goal/context*: If her order is deferred, she needs to know early and clearly, not discover it when no truck shows up.
* *Arrangement*: Pushed proactively as soon as the dispatcher's allocation is finalized, stating the outlet was deferred, and — where the dispatcher recorded one — a plain-language reason and the expected next-run date.
* *Workflow/constraints*: Directly answers the booklet's requirement for "clear notice when an order is deferred," and is the store-manager-facing half of the Degradation Scenario (see Section 4).
* *Next*: She can acknowledge it; no further action required until the next order cycle.

**Screen 5 — Confirm Receipt**

* *Goal/context*: After delivery, Fathima needs to confirm what actually arrived and flag any issue (damaged, short, wrong item).
* *Arrangement*: A checklist against the original order (what was ordered vs what arrived), with a single tap to flag a discrepancy rather than a free-text-only report.
* *Workflow/constraints*: Implements the booklet's "confirm receipt" workflow stage and gives the system a proof-of-delivery record that doesn't depend on the driver's memory alone.
* *Next*: Closes the order lifecycle for that delivery.

### 2.2 Dispatcher

**Screen 1 — Order Queue**

* *Goal/context*: After the 4 PM cutoff, Nadeeka needs every confirmed order in one place instead of assembling it from calls and messages.
* *Arrangement*: Filterable by brand/district/temperature requirement, with a demand-vs-capacity indicator at the top so she knows within seconds whether today is a normal day or a shortfall day.
* *Workflow/constraints*: Implements "bring confirmed orders into one queue" from the booklet's workflow table, and is the entry point for the "Assign served orders to vehicles and trips; identify deferred orders" stage.
* *Next*: Moves into the Allocation / Planning view.

**Screen 2 — Allocation / Planning View**

* *Goal/context*: This is where she assigns orders to vehicles and trips. (Detailed in Section 4 as the Capacity Shortfall degradation screen, since on a shortfall day this view carries most of the design weight.)
* *Arrangement*: Live constraint checking as she works, so a violation is caught before it's committed rather than after.
* *Workflow/constraints*: Directly implements all seven feasibility rules from the booklet (brand/district homogeneity per trip, refrigeration, van access, home depot, whole-order assignment, capacity caps, trip/time budgets).
* *Next*: Finalizing the plan pushes stop sequences to loaders and triggers deferral notices to store managers.

**Screen 3 — Deferral Summary**

* *Goal/context*: Nadeeka needs a single place to see every deferred order and be sure each one has a recorded reason, rather than a scattered set of "didn't fit" decisions.
* *Arrangement*: One list, one reason field per row, distinguishing constraint-forced deferrals from her own judgment calls.
* *Workflow/constraints*: Answers the booklet's statement that "decisions made under pressure can leave the same outlet unserved on consecutive runs" — this screen is what prevents that from happening silently, since `deferred_yesterday` and `days_since_last_served` are visible here.
* *Next*: Feeds the store-manager deferral notices (Store Manager Screen 4) and stands as the written record referenced in the Datathon Task 2B prioritization policy.

**Screen 4 — Live Operations View**

* *Goal/context*: Once vehicles leave, Nadeeka currently has no shared view of progress and learns about problems only after a driver reaches the outlet.
* *Arrangement*: Per-vehicle/trip status (in transit, at stop, completed), with loader- and driver-flagged issues surfaced as soon as they're reported.
* *Workflow/constraints*: Addresses the booklet's stated problem that "dispatchers usually learn about a problem only after a driver has reached the outlet."
* *Next*: Any flagged issue may require her to adjust plans for remaining stops or the next run.

**Screen 5 — Capacity Planning View**

* *Goal/context*: Nadeeka currently has no way to anticipate vehicle, driver, or refrigerated-capacity needs ahead of paydays or festivals.
* *Arrangement*: A forward-looking view over upcoming weeks, intended to consume the Datathon Task 2A demand forecasts (total and chilled volume by depot/brand/week) once available.
* *Workflow/constraints*: Implements the booklet's final workflow stage, "Plan future capacity … Use demand forecasts to plan vehicles, drivers, and refrigerated capacity."
* *Next*: Informs longer-term fleet and staffing decisions outside the daily allocation cycle.

*Assumption flagged*: the booklet does not specify how forecast data reaches this screen technically (e.g. file import vs. live pipeline) — for the Designathon this can be shown as a static forward view; the integration mechanism is a Hackathon decision, not a Designathon one.

### 2.3 Loader

**Screen 1 — Dock Queue**

* *Goal/context*: Sampath needs to know which vehicles are due to load, and in what order, at the start of a shift.
* *Arrangement*: A simple prioritized list by departure time, readable at a glance on a shared tablet.
* *Workflow/constraints*: Implements the booklet's "Load for the planned stop sequence" workflow stage.
* *Next*: Selecting a vehicle opens its Stop-Sequence Loading List.

**Screen 2 — Stop-Sequence Loading List**

* *Goal/context*: Sampath needs to load in an order that supports unloading (last-stop-first), and the list must reflect the current plan even if the dispatcher changed it after printing — the exact failure the booklet calls out ("printed loading lists can become outdated when plans change").
* *Arrangement*: A live, per-vehicle/trip list ordered by stop sequence, always synced to the dispatcher's committed plan rather than a static printout.
* *Workflow/constraints*: Directly removes the stated "outdated printed list" problem and supports correct physical loading order.
* *Next*: Once loaded, he either proceeds to dispatch or uses Screen 3 if something's wrong.

**Screen 3 — Flag Shortfall / Damage**

* *Goal/context*: Sampath needs a fast way to report a missing or damaged item before the vehicle leaves, not after.
* *Arrangement*: A low-friction, few-tap flag against a specific order line, routed immediately to the dispatcher and blocking or warning before departure.
* *Workflow/constraints*: Implements "Needs to flag missing or damaged items before a vehicle leaves" from the booklet's role description.
* *Next*: The dispatcher sees the flag on the Live Operations View (Dispatcher Screen 4) and can adjust the plan before the vehicle departs.

### 2.4 Driver

**Screen 1 — Today's Stops**

* *Goal/context*: Ruwan needs a simple, glanceable list of stops for his current trip, usable one-handed and safely while stopped.
* *Arrangement*: One trip visible at a time, large touch targets, minimal text.
* *Workflow/constraints*: Implements "Follow the route and record each stop" from the booklet's workflow table, and the design note "interactions for use when safely stopped."
* *Next*: Tapping a stop opens Stop Detail.

**Screen 2 — Stop Detail**

* *Goal/context*: Before approaching an outlet, Ruwan needs to know its access conditions (dock type, parking constraint) and delivery window, and what's on board for that stop.
* *Arrangement*: Access and window information surfaced first, since a van_only or mall-window mismatch is exactly the kind of problem the booklet flags as a real operating constraint.
* *Workflow/constraints*: Domain accuracy point — reflects `dock_type`, `parking_constraint`, and `mall_window` fields from `outlets.csv`.
* *Next*: On arrival, he proceeds to Record Outcome.

**Screen 3 — Record Outcome**

* *Goal/context*: Ruwan needs to record delivered / attempted / issue with proof of delivery, so disputes don't depend on memory — stated directly in the booklet's driver role description.
* *Arrangement*: One-tap outcome selection plus a proof-of-delivery capture (signature or photo), minimizing typing.
* *Workflow/constraints*: Implements "record delivery outcomes and proof of delivery" and feeds the Store Manager's Confirm Receipt screen.
* *Next*: Advances to the next stop, or — if offline — queues the record locally (Screen 4).

**Screen 4 — Offline State**

* *Goal/context*: Coverage drops in hill country and the Kandy corridor; Ruwan must keep working exactly as normal and have it sync later.
* *Arrangement*: The same screens as above, with a visible "not yet synced" indicator rather than a separate offline mode — this is a deliberate design choice: parallel offline/online flows would double the interface surface for no benefit, and the booklet asks for work to "remain usable offline" and "reconcile when the connection returns," not for a distinct experience.
* *Workflow/constraints*: Implements the booklet's connectivity requirement directly.
* *Next*: On reconnect, queued records sync automatically and the indicator clears; this is worth calling out explicitly as a "sync confirmation" moment in the prototype so judges can see it happen.

---

## 3. End-to-End Flow Consistency Check

Tracing one order through all four roles confirms the flows connect as the booklet requires ("a dispatcher's decision should reach the loader, and a driver's delivery record should give the store manager information they can act on"):

Store Manager places order → Dispatcher's Order Queue picks it up → Dispatcher's Allocation view assigns it to a vehicle/trip (or defers it) → if served, Loader's Stop-Sequence List reflects the assignment → Driver's Today's Stops includes it → Driver records the outcome → Store Manager's Confirm Receipt screen closes the loop.

If deferred instead: Dispatcher's Deferral Summary records a reason → Store Manager's Deferral Notice fires → no loader/driver screens are touched for that order. This is the consistency point examined in Section 4.

---

## 4. Primary Degradation Scenario — Consistency Across Roles

### Name: "Capacity Shortfall" (Degradation Scenario A — demand exceeds available fleet capacity)

**Why it matters:**
On most days Waypoint's 60 vehicles cannot serve every confirmed order. Today this decision lives entirely in one dispatcher's head and a spreadsheet — there is no record of which constraint forced a deferral, so the same outlet can be skipped two days in a row without anyone noticing, and store managers get no warning. This screen turns an invisible, ad-hoc judgment call into a visible, explainable one: it shows the dispatcher exactly which resource is binding (refrigerated capacity, van count, a district's time budget, a specific vehicle's fuel quota), lets her compare the cost of alternative allocations before committing, and forces a recorded reason for every deferral. That record is what lets Waypoint explain a decision to a store manager, avoid repeat-deferring the same outlet, and feed the next day's plan.

**Fully developed screen — Dispatcher's Capacity Shortfall (Allocation) view:**

* **Header strip**: today's date, total confirmed orders, total available capacity (vehicles, refrigerated slots, van slots), and a single "at risk" count.
* **Binding-constraint panel**: plain-language statement of what's limiting service, e.g. "3 of 16 refrigerated vehicles are in the workshop" or "Gampaha Fresh trips are over the 270-minute pre-dawn budget." Shown first, so the dispatcher understands within seconds that today is a shortfall day and roughly why.
* **Order queue, grouped by brand/district**: outlet, temperature requirement, access constraint, size, and `deferred_yesterday` / `days_since_last_served` flags, so consecutive deferrals are visible before they happen.
* **Allocation workspace**: assign orders to vehicle + trip with live constraint checking (capacity, brand/district homogeneity, temperature, van access, home depot, time budget) — no silent invalid assignment.
* **Deferral panel**: every unassigned order requires a reason before the plan can be finalized, distinguishing system-forced deferrals from the dispatcher's own judgment calls.
* **Commit action**: finalizing pushes stop sequences to loaders and fires deferral notices to store managers.

**Consistency across the other three roles** (this is what makes it one degradation scenario rather than an isolated screen):

* **Store Manager**: receives the Deferral Notice (Screen 2.1-4) proactively once the dispatcher commits the plan — same event, same reason text where one was recorded, same expected next-run date. The store manager never learns about a deferral by a truck simply not arriving.
* **Loader**: for orders that *are* served despite the shortfall, the Stop-Sequence Loading List (Screen 2.3-2) reflects only the committed allocation — loaders never load for an order the dispatcher deferred, since the list is live rather than pre-printed.
* **Driver**: sees only the finalized, feasible set of stops on Today's Stops (Screen 2.4-1) — the shortfall is fully resolved by the time it reaches the driver. The degradation is absorbed and made visible at the dispatcher stage, not pushed downstream as confusion for the driver or store manager.

*Assumption*: the booklet does not specify the exact wording or timing (immediate vs. batched) of the deferral notice to store managers. We assume the notice is sent as soon as the dispatcher commits the plan. This is a reasonable design choice, not a booklet requirement.

**Secondary scenario (not fully developed)**: "Driver loses connectivity mid-route". The offline behaviour is shown on the Driver's Offline State screen (Section 2.4, Screen 4). We chose to develop one failure scenario in full, since the booklet says response quality matters more than the number of scenarios.

---

## 5. Booklet Compliance Check

| Requirement (Challenge Booklet)                                                       | Status                                                                                                    |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Personas for all four roles, grounded in working conditions and needs                 | Complete (Section 1)                                                                                      |
| Screen flows per role, one-paragraph rationale per screen                             | Complete (Section 2)                                                                                      |
| At least one fully developed degradation screen, named, with rationale                | Complete (Section 4)                                                                                      |
| Connect role-specific experiences end-to-end                                          | Complete (Section 3)                                                                                      |
| High-fidelity prototype (design tool of choice)                                       | Complete — live at https://hafees14.github.io/timesware-tech-triathlon-2026/                              |
| Demo video (3–5 min, unlisted YouTube, walkthrough + assumptions)                     | Complete — https://youtu.be/R66atItt5bE (unlisted)                                                        |
| AI tool disclosure                                                                    | Complete — see Section 6                                                                           |
| Core tradeoff explanation (optional, ≤1 page/diagram)                                 | Complete — see Section 7                                                                                  |
| Style guide (optional)                                                                | Complete — see Section 8                                                                                  |
| Submission file naming: `TeamName_Designathon` → zipped as `TeamName_Designathon.zip` | Complete: packaged as `Timesware_Designathon.zip` |

---

## 6. AI Tool Disclosure

**Team:** Timesware, two members: MFM Ayyash and MKH Hafees.

**Tools used:** Claude (Anthropic), Figma, and NotebookLM (Google). GitHub Copilot was not used.

**AI-assisted work:**

* Drafting the first version of the persona text, screen-flow rationale paragraphs, and the degradation scenario write-up, which the team reviewed and edited
* Writing much of the HTML/CSS/JS for the high-fidelity prototype (role screens, design token system, the allocation/validation checks on the dispatcher's Capacity Shortfall screen, the offline-to-sync simulation)
* Restyling passes (icon system, visual treatment of the degradation banner) and a design-tell review (removing generic patterns like middle-dot-joined meta text and all-caps labels)
* Reading the challenge booklet and our screen text to list requirements, gaps, and cross-role inconsistencies (dates, order IDs, stop counts, arrival times), and helping us fix them
* Troubleshooting the GitHub Pages deployment (diagnosing the Jekyll build issue, recommending the `.nojekyll` fix)
* The Figma file: produced by capturing the HTML prototype into Figma, then organised into pages by the team
* The demo video: the team wrote the script and captured screenshots of the prototype, and NotebookLM was used to produce the video from them

**What was not AI-assisted / where the team's judgment was:**

* Which degradation scenario to build out fully (Capacity Shortfall, chosen over the connectivity-loss and shortfall-flagging alternatives that were also drafted), what to prioritise and cut from each role's screen list, and the choice of assisted planning over full automation
* The workflow across the four roles and the information architecture
* Choosing between AI-proposed options, reviewing and approving every screen, rationale paragraph, and structural choice, and correcting mistakes
* The demo video script and the choice of screenshots
* Repository structure, naming, and hosting decisions

**How the tools were used:** Claude was used as a drafting and coding assistant under the team's direction, proposing options, writing first drafts of content and code, and revising based on explicit feedback, rather than as an autonomous decision-maker. NotebookLM only turned the team's own script and screenshots into a video. The rules and limits shown in the prototype (4 PM cutoff, 270-minute pre-dawn budget, 16 refrigerated vehicles, van-only access) come from the Challenge Booklet. Outlet names, order numbers, vehicle capacities, and quantities are synthetic and illustrative. The team is accountable for the final submitted content.

---

## 7. Core Tradeoff: Dispatcher Control vs. Automatic Planning

Waypoint's dispatchers hold knowledge that no data file contains, such as gate rules, outlet habits, and vehicle quirks. A fully automatic plan would be hard to explain and hard to trust, while today's spreadsheet is the source of the problems in the brief. We chose **assisted planning**. The Allocation view checks capacity, refrigeration, depot, vehicle access, and the 270-minute pre-dawn budget as Nadeeka works, and blocks invalid moves with a plain reason. She makes the final decision, and every deferral needs a recorded reason that flows to the store manager's notice.

* **Cost:** more effort for the dispatcher at planning time.
* **Why we accepted it:** the brief asks for decisions Waypoint can explain, and a repeated skip of the same outlet needs a person to notice and act.

---

## 8. Style Guide

| Item | Values |
| --- | --- |
| Neutrals | Ink 900 `#12151b`, Ink 600 `#3d4753`, Ink 400 `#7c8894`; surfaces `#ffffff`, `#f7f7f5`, `#eeefec`; border `#e0e2e1` |
| Brand | Amber `#b3730a` (hover `#d68f1f`, dark `#7a4d05`, tint `#fbeed9`); navy `#0e141d` |
| Status colours (state only, never decoration) | Success `#1c8a56`, Warning `#b5680a`, Danger `#c23b3b`, Info `#2472a4`, Chilled `#1f7a8c`, each with a tint |
| Type | UI: Inter. Display: Space Grotesk. Data: IBM Plex Mono. Sizes 12–36 px; weights 400, 500, 600, 700 |
| Spacing | 4 px base scale: 4, 8, 12, 16, 20, 24, 32, 40, 56 |
| Radius | 5, 8, 12, 16 px, and pill |
| Motion | 120, 200, and 420 ms with one easing curve |
| Components | Status chips, KPI cards, filterable tables, vehicle cards with rule checks, banners (Capacity Shortfall, Offline, Load last stop first), outcome buttons, proof-of-delivery buttons |
| Role consistency | Same status names, order references, and status colours on all four roles. Driver and loader screens use larger touch targets. |
