# ML-IDS pipeline dashboard prototype

This desktop and mobile web prototype combines the recorded ML-IDS pipeline into seven tabs: Overview, Data, Experiments, Training, Model review, Serving, and Monitoring. The right rail explains the selected stage and links to relevant source details.

The displayed AWS results are a **historical snapshot checked on 25 September 2026**, sourced from the repository's [AWS deployment record](../../docs/aws-deployment-status.md). This app has no live AWS connection. It never starts a job, approves a package, or deploys an endpoint. Those controls review a target, require confirmation, then show the existing manual workflow or a command for use outside the prototype.

The Data tab keeps Glue/Athena analytics separate from the raw S3 input used by SageMaker. The Experiments tab covers all five local models. Training and Model review keep the AWS classical and LSTM paths distinct, including their different evaluation units.

For local development, run these commands inside this folder:

    npm install
    npm run dev

The main UI is in [src/App.jsx](src/App.jsx), recorded evidence and guidance in [src/data.js](src/data.js), and visual styles in [src/styles.css](src/styles.css). The selected design comparison and browser QA are in [design-qa.md](design-qa.md).
