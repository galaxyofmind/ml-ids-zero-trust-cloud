# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## Selected dashboard direction

- The project owner/reviewer is the primary audience. Use plain-language summaries with AWS service details one level deeper.
- Match the selected combined Image Gen mock: pipeline journey and model evidence ledger in the main area, with a persistent contextual “Summary & guidance” rail beside it.
- Cover the full pipeline in Overview, Data, Experiments, Training, Model review, Serving, and Monitoring tabs. Keep the layout clear and avoid crowding a single screen.
- Show the source and observation time for every operational claim. The recorded AWS evidence is a historical 25 September 2026 snapshot, not live state.
- Keep local five-model experiments, AWS classical models, and AWS LSTM distinct. Glue/Athena analytics is parallel to model training. LSTM window scores are not directly comparable with flow-level scores.
- The intended controlled actions are start training, approve a model package, and deploy. Each needs a separate review of target, permissions, and effects before an AWS write. The current prototype has no AWS write connection.
