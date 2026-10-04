# Architecture

```mermaid
flowchart LR
  subgraph Client
    P[Designathon prototype<br/>static HTML/CSS/JS (Designathon) + js/wp-live.js glue]
  end
  subgraph Backend[FastAPI container]
    S[Static file server]
    D["GET /js/data.js<br/>wpdata.py adapter"]
    A[auth: JWT + role guards]
    R[dispatcher / loader / driver / store routers]
    E[engine.py<br/>allocate + validate_plan + layout]
  end
  DB[(MySQL 8)]
  CSV[/data/*.csv<br/>shared datasets/]
  P -->|pages| S
  P -->|script tag| D
  P -->|fetch /api + JWT| A --> R --> E
  R --> DB
  D --> DB
  CSV -->|seed on first start| DB
```

## Key design choices
- **Frontend is the master.** The backend reproduces the prototype's data contract (`WP_DATA`) instead of asking the UI to change. The only frontend addition is `js/wp-live.js` (one `<script>` line per page) which wires the buttons to the API.
- **Demo sign-in.** The design has no login screen (Home is the role picker), so each page signs in as its role's seeded account through `GET /api/auth/demo?role=` (switch off with `DEMO_LOGIN=0`; real login stays at `POST /api/auth/login`).
- **One engine, three uses:** auto-allocation, validation of hand edits, and (same column names) the Datathon peak-day task.
- **Cross-role gating is enforced in the API:** a driver cannot depart before the loader releases the vehicle; loader release is blocked by unresolved shortfalls; receipts only after a recorded delivery.
- **Offline:** the driver phone writes every outcome to a local queue (`localStorage`, key `wp_queue_v1`) first; when signal returns it posts the queue to `POST /api/driver/sync`. The server is idempotent per `client_uuid`, keeps device timestamps and applies "driver wins if recorded before the deferral".

```
Frontend (static pages + wp-live.js)  ->  FastAPI (routers + engine)  ->  MySQL 8 (SQLAlchemy)
```
