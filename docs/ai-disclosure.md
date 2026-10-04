# AI tool disclosure (Hackathon)

- **Tool:** Claude (Anthropic), used in a chat interface. No competition dataset was sent to any external service: the AI worked only on code, the Designathon prototype files and **synthetic** fixture CSVs that follow the booklet's schema. The real CSVs are read locally by the seed script only.
- **AI-assisted:** the FastAPI backend (data model, allocation engine, seed script, REST API, the `/js/data.js` adapter), `frontend/js/wp-live.js` (the glue that connects the Designathon buttons to the API and the offline queue), the pytest and jsdom end-to-end tests, Docker files and these docs.
- **Not AI-assisted:** the Designathon UI/UX design itself (personas, flows, screens, visual language) - the team's earlier submission, kept unchanged.
- **How it was used:** the team gave Claude the Challenge Booklet, the submitted prototype and the Hackathon brief; Claude proposed and wrote code, ran the tests, and reported failures, which were fixed iteratively.
- **Verification:** automated tests (`tests/test_e2e.py`, `tests/browser/flow.test.mjs`) run all four roles end to end against SQLite with synthetic data. `docker compose` / MySQL and the real CSVs must be checked by the team.
- **Team review:** *[Team: describe what you reviewed, changed or rejected before submitting.]*
