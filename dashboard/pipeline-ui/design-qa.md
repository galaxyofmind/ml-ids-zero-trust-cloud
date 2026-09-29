# Dashboard design QA

**Source visual truth:** /home/origin/.codex/generated_images/01a0eb86-bddd-75e2-abd2-6f9204dad3d1/exec-27f4c4c3-cd20-42db-959b-b7ed78362b3b.png

**Browser-rendered implementation:** [qa/overview-final.jpg](qa/overview-final.jpg)

**State:** Overview tab, historical snapshot, no dialog open. The prototype is intentionally not connected to AWS.

**Viewport and normalization:** Browser CSS viewport 1440 × 1024 at device pixel ratio 1. Source image 1487 × 1058 pixels; browser capture 1425 × 1013 pixels (the browser capture excludes scrollbar and edge pixels). Both were normalized to 1440 × 1024 for comparison. Mobile check used a 390 × 844 CSS viewport and [full-page capture](qa/mobile-full.jpg); document width was 390 pixels.

**Comparison evidence:** [Full-view side-by-side](qa/comparison.png), [header and generated brand mark](qa/focus-header.png), [journey and model ledger](qa/focus-main.png), [guidance rail](qa/focus-rail.png).

## Findings

No actionable P0, P1, or P2 differences remain.

- **Fonts and typography:** Inter matches the mock's clean sans-serif hierarchy. The final pass increased stage, table, and guidance text to keep the dense evidence readable.
- **Spacing and layout:** The desktop split, header, stage journey, model ledger, and persistent right rail follow the selected mock. The complete overview ledger and unit note remain visible at the design viewport. Mobile stacks the guidance below the main content.
- **Colors and tokens:** White surface, navy text, teal actions, and restrained amber evidence note match the source direction. Status color is supplemented with text.
- **Image and icon quality:** The generated transparent shield at [public/assets/brand-mark.png](public/assets/brand-mark.png) replaces the provisional library mark. Standard UI icons use Phosphor. The asset is crisp at header size.
- **Copy and content:** The mock's invented identity, fictional activity, and implied live status were replaced with a dated repository snapshot and explicit “not connected” status. The LSTM evaluation-unit warning remains prominent.
- **Interactions and responsiveness:** All seven tabs opened with the expected heading. The reviewer path, LSTM training review, SVM v5 approval review, and candidate deployment review worked. Invalid endpoint names cannot advance, and editing the target resets confirmation. Browser console error log was empty. Mobile has no page-width overflow; model evidence becomes readable stacked rows.

## Comparison history

1. **P2 — overview content sat too low.** The [first desktop capture](qa/overview-initial.jpg) wrapped the subtitle and pushed the model ledger toward the fold. Fixed the snapshot placement and tightened the journey/ledger rhythm. The corrected result is visible in [qa/overview-final.jpg](qa/overview-final.jpg) and [qa/focus-main.png](qa/focus-main.png).
2. **P2 — mobile model evidence required horizontal table scrolling.** Approval and serving were hidden offscreen. Changed the table to labeled model rows below 620 pixels. The post-fix result is [qa/mobile-full.jpg](qa/mobile-full.jpg).
3. **P2 — provisional brand icon differed from the selected mock.** Generated a transparent shield based on the source mark and placed it in the header. The post-fix comparison is [qa/focus-header.png](qa/focus-header.png).

## Follow-up polish

- P3: The analytics branch is a horizontal callout rather than the mock's compact split connector. This keeps the S3-to-Glue/Athena relationship explicit.
- P3: The release sequence is more compact than the mock so the guidance remains visible at the design viewport.

**Final result: passed**
