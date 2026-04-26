# Internal notes (historical)

Scratch documents that drove past iterations. Kept for audit/history,
**not** part of the published documentation site.

VitePress does not pick them up: `docs/.vitepress/config.js` only
references files explicitly listed in the sidebar (`/guide/*` and
`/api/*`); everything under `docs/internal/` is invisible to the
generated site.

Contents:

| File | What it is |
|------|------------|
| `ROAD_TO_1000.md` / `.html` | An aspirational launch plan written before v1.0; some claims have been overtaken by reality. |
| `walkthrough.md` | Phase-5 commit narrative (Sentry / cmdk / joyride). Italian. |
| `implementation_plan.md` | Plan that produced the phase-5 work — corresponds to the tasks in `task.md`. |
| `task.md` | Phase-5 task checklist (all completed). |

Future scratch / planning documents should land here too, never in the
repo root, so visitors landing on the project see code and a focused
README — not internal todos.
