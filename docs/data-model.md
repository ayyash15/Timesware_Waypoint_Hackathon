# Data model

```mermaid
erDiagram
  OUTLETS ||--o{ ORDERS : places
  OUTLETS ||--o{ USERS : "store manager of"
  VEHICLES ||--o{ USERS : "driver default"
  PLANS ||--o{ TRIPS : contains
  VEHICLES ||--o{ TRIPS : runs
  TRIPS ||--o{ TRIP_STOPS : sequences
  ORDERS ||--o| TRIP_STOPS : "served by"
  PLANS ||--o{ DEFERRALS : records
  ORDERS ||--o{ DEFERRALS : "deferred as"
  TRIPS ||--o{ LOADING_ISSUES : flags
  ORDERS ||--o{ LOADING_ISSUES : about
  ORDERS ||--o| RECEIPTS : "confirmed by"
  DISTRICT_TRAVEL }o--|| OUTLETS : "by district"
  SERVICE_ALLOWANCE }o--|| OUTLETS : "by brand+dock"
```

Reference tables seeded from the shared CSVs: `outlets`, `vehicles`, `calendar_days`, `district_travel`, `service_allowance`.
Workflow tables: `users`, `orders`, `plans`, `trips`, `trip_stops` (carries outcome, POD photo, `client_uuid`, device `recorded_at`, `synced_at`, `conflict_note`), `deferrals` (reason code, text, unavoidable flag, decided_by, rescheduled date), `loading_issues`, `receipts`, `notifications`.

Order status flow: `confirmed → planned → loaded → in_transit → delivered | failed → received | issue`, or `deferred`.
