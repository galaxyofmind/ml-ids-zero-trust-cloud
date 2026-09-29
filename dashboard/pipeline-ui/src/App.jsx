import { useEffect, useState } from "react";
import {
  ArrowRight, ArrowSquareOut, ChartBar, ChartLineUp, Check, CheckCircle,
  ClipboardText, Cloud, Copy, Database, Gear, Info, LockKey, Play,
  WarningCircle, X,
} from "@phosphor-icons/react";
import {
  CLOUDWATCH_CONSOLE, GITHUB_WORKFLOW, LOCAL_MODELS, MODELS, NAV_ITEMS,
  REGION, SAGEMAKER_CONSOLE, SNAPSHOT_DATE, STAGE_GUIDANCE,
} from "./data.js";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";

const REPO = "https://github.com/galaxyofmind/ml-ids-zero-trust-cloud";
const icon = (Component, size = 20, weight = "regular") =>
  <Component size={size} weight={weight} aria-hidden="true" />;

function ExternalLink({ href, children, className = "" }) {
  return <a className={"external-link " + className} href={href} target="_blank" rel="noreferrer">
    {children} {icon(ArrowSquareOut, 15)}
  </a>;
}

function Status({ children, tone = "neutral" }) {
  return <span className={"status status-" + tone}>{children}</span>;
}

function SectionHeading({ eyebrow, title, description, aside }) {
  return <div className="section-heading"><div><div className="eyebrow">{eyebrow}</div>
    <h1>{title}</h1><p>{description}</p></div>{aside}</div>;
}

function Snapshot() {
  return <span className="snapshot"><span className="snapshot-dot" />
    Historical snapshot · checked {SNAPSHOT_DATE}</span>;
}

function Journey({ navigate }) {
  const stages = [
    ["Data", Database, "Raw files in S3", "S3"],
    ["Training", Gear, "Build and evaluate", "SageMaker"],
    ["Model review", ClipboardText, "Inspect package evidence", "Registry"],
    ["Serving", Cloud, "Approved endpoints", "SageMaker"],
    ["Monitoring", ChartLineUp, "Drift and alarm evidence", "CloudWatch"],
  ];
  return <div className="journey-wrap"><div className="journey" aria-label="Pipeline stages">
    {stages.map(([name, Icon, subtitle, source], index) =>
      <div className="journey-pair" key={name}>
        <button className={"journey-stage " + (name === "Model review" ? "attention" : "")}
          onClick={() => navigate(name)}>
          <span className="journey-icon">{icon(Icon, 34)}</span>
          <strong>{name}</strong><span className="journey-subtitle">{subtitle}</span>
          <span className="service-tag">{source}</span>
        </button>
        {index < stages.length - 1 && icon(ArrowRight, 20)}
      </div>)}
  </div><button className="analytics-branch" onClick={() => navigate("Data")}>
    <span className="analytics-icon">{icon(ChartBar, 25)}</span>
    <span><strong>Analytics runs in parallel</strong>
      <small>Glue and Athena explore curated data. AWS training reads raw NSL-KDD from S3.</small></span>
    {icon(ArrowRight, 18)}
  </button></div>;
}

function ModelTable({ selectedModel, selectModel, navigate }) {
  return <div className="table-scroll"><table className="model-table"><thead><tr>
    <th>Model</th><th>Official test F1</th><th>Evaluation unit</th><th>Approval</th><th>Serving</th>
  </tr></thead><tbody>{MODELS.map(m => <tr key={m.id}
    className={(m.id === "lstm" ? "lstm-row " : "") + (selectedModel === m.id ? "selected-row" : "")}>
    <td data-label="Model"><button className="table-model" onClick={() => { selectModel(m.id); navigate("Model review"); }}>
      <strong>{m.name}</strong><small>{m.fullName}</small></button></td>
    <td data-label="Official test F1" className="metric-value">{m.f1.toFixed(3)}</td>
    <td data-label="Evaluation unit">{m.unit}</td>
    <td data-label="Approval"><span className="table-status">{icon(CheckCircle, 19, "fill")} Approved</span></td>
    <td data-label="Serving">{m.endpoint ? <span className="table-status historical">{icon(Info, 18)}
      <span>Recorded endpoint<small>Current status unknown</small></span></span>
      : <span className="muted">No dedicated endpoint</span>}</td>
  </tr>)}</tbody></table></div>;
}

function UnitNote() {
  return <div className="unit-note">{icon(WarningCircle, 25, "fill")}<div>
    <strong>Window-level scores cannot be compared directly with flow-level scores.</strong>
    <span>LSTM evaluates 20-flow file-order windows; RF, SVM and XGBoost evaluate individual flows.</span>
  </div></div>;
}

function Overview({ navigate, selectedModel, selectModel }) {
  return <><SectionHeading eyebrow="INTRUSION DETECTION"
    title="From data to real-world protection"
    description="Follow the recorded path from source data to reviewed models, serving and monitoring."
    aside={<Snapshot />} />
    <Journey navigate={navigate} />
    <div className="ledger-head"><div><h2>Model performance <span>(AWS models)</span></h2>
      <p>Official NSL-KDD test results. Historical evidence from {SNAPSHOT_DATE}.</p></div>
      <Status><span className="snapshot-dot" /> Not connected to AWS</Status></div>
    <ModelTable selectedModel={selectedModel} selectModel={selectModel} navigate={navigate} />
    <UnitNote /></>;
}

function FactRows({ rows }) {
  return <div className="fact-rows">{rows.map(([label, value]) =>
    <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>;
}

function DataView({ navigate }) {
  return <><SectionHeading eyebrow="DATA FOUNDATION" title="Two uses of source data"
    description="Model training and analytics share raw S3 inputs, then follow separate paths."
    aside={<Snapshot />} />
    <div className="notice info-notice">{icon(Info, 22)}
      <span>The Glue/Athena tables do not feed either SageMaker model-training path.</span></div>
    <div className="two-column">
      <section className="detail-section"><span className="source-icon">{icon(Database, 28)}</span>
        <h2>Raw data in Amazon S3</h2><p>NSL-KDD training and official-test files are the AWS model inputs.</p>
        <FactRows rows={[["Training file", "KDDTrain+ · 125,973 flows"],
          ["Official test", "KDDTest+ · 22,544 flows"], ["Model input", "Raw NSL-KDD records"]]} />
        <button className="text-action" onClick={() => navigate("Training")}>
          See how models use the files {icon(ArrowRight, 17)}</button></section>
      <section className="detail-section"><span className="source-icon">{icon(ChartBar, 28)}</span>
        <h2>Analytics with Glue + Athena</h2><p>A separate ETL and query branch creates curated tables for exploration.</p>
        <FactRows rows={[["NSL-KDD", "Glue ETL and Athena query succeeded"],
          ["UNSW-NB15", "Separate analytics dataset and table"],
          ["UNSW train rows", "175,341"]]} />
        <div className="service-links">
          <ExternalLink href={"https://" + REGION + ".console.aws.amazon.com/glue/home?region=" + REGION}>Open Glue</ExternalLink>
          <ExternalLink href={"https://" + REGION + ".console.aws.amazon.com/athena/home?region=" + REGION}>Open Athena</ExternalLink>
        </div></section>
    </div><div className="subsection-heading"><h2>Data checks</h2>
      <p>Evidence to inspect before interpreting a model run.</p></div>
    <div className="check-list"><span>{icon(CheckCircle)} Dataset and manifest</span>
      <span>{icon(CheckCircle)} Official test kept separate</span>
      <span>{icon(CheckCircle)} Schema and selected features</span></div>
    <SourceFooter href={REPO + "/blob/master/docs/aws-deployment-status.md"} label="AWS deployment record" />
  </>;
}

function ExperimentsView({ navigate }) {
  return <><SectionHeading eyebrow="LOCAL EXPERIMENTS" title="Five models in one local workflow"
    description="These experiments use local arrays and MLflow; they are separate from the AWS results."
    aside={<Status tone="amber">Driver needs repair</Status>} />
    <div className="notice warning-notice">{icon(WarningCircle, 23)}<span>
      <strong>The all-model driver currently fails at import.</strong> It requests
      <code> compute_all_metrics</code>, which is missing from <code>src/evaluate.py</code>.
      No fresh local run is claimed here.</span></div>
    <div className="subsection-heading"><h2>Intended local model sequence</h2>
      <p>Each trainer saves a local artifact and requests named MLflow registration.</p></div>
    <div className="local-model-list">{LOCAL_MODELS.map((m, i) =>
      <div className="local-model-row" key={m.name}><span className="row-index">{i + 1}</span>
        <strong>{m.name}</strong><span>{m.unit}</span><code>{m.artifact}</code></div>)}</div>
    <div className="detail-section compact-detail"><h2>Important difference for LSTM</h2>
      <p>The local LSTM makes 20-row windows after a shuffled split and uses the first row's
        label. AWS LSTM uses file-order windows and the last row's label.</p></div>
    <button className="text-action" onClick={() => navigate("Training")}>
      View the recorded AWS runs {icon(ArrowRight, 17)}</button>
    <SourceFooter href={REPO + "/blob/master/src/train_mlflow.py"} label="Local training driver" />
  </>;
}

function PathSteps({ lstm }) {
  const steps = lstm
    ? ["Raw NSL-KDD in S3", "Build 20-flow windows", "Train and evaluate", "Register separately", "Human approval"]
    : ["Raw NSL-KDD in S3", "Fit preprocessing", "Train and evaluate", "F1 ≥ 0.70 gate", "Human approval"];
  return <div className="path-steps">{steps.map((step, i) =>
    <div className="path-step" key={step}><span className="step-number">{i + 1}</span>
      <span>{step}</span>{i < steps.length - 1 && icon(ArrowRight, 16)}</div>)}</div>;
}

function TrainingView({ openAction }) {
  const [path, setPath] = useState("classical");
  const listed = MODELS.filter(m => path === "lstm" ? m.id === "lstm" : m.id !== "lstm");
  return <><SectionHeading eyebrow="SAGEMAKER TRAINING" title="Two AWS training paths"
    description="Both read raw NSL-KDD data from S3. Preparation, evaluation and registration differ."
    aside={<Snapshot />} />
    <div className="segmented" role="tablist" aria-label="Training path">
      <button role="tab" aria-selected={path === "classical"} className={path === "classical" ? "active" : ""}
        onClick={() => setPath("classical")}>Classical · RF, SVM, XGBoost</button>
      <button role="tab" aria-selected={path === "lstm"} className={path === "lstm" ? "active" : ""}
        onClick={() => setPath("lstm")}>LSTM · 20-flow windows</button></div>
    <section className="path-panel"><div className="path-title"><span className="source-icon">
      {icon(path === "lstm" ? ChartLineUp : ChartBar, 29)}</span><div>
      <h2>{path === "lstm" ? "LSTM path" : "Classical model path"}</h2>
      <p>{path === "lstm" ? "One TensorFlow Processing step; registration follows in a separate script."
        : "Preprocessing and fitting run in SageMaker Processing under the account quota."}</p>
    </div></div><PathSteps lstm={path === "lstm"} />
      <p className="path-footnote">{path === "lstm"
        ? "Official test: 1,127 file-order windows of 20 flows, labeled by the last flow. Four leftover flows are dropped."
        : "Official test: 22,544 untouched KDDTest+ flows. Training-row limits vary by model."}</p></section>
    <div className="subsection-heading"><h2>Recorded executions</h2>
      <p>Checked on {SNAPSHOT_DATE}; current execution state is not connected.</p></div>
    <div className="run-list">{listed.map(m => <div className="run-row" key={m.id}>
      <div><strong>{m.name}</strong><span>{m.pipeline}</span></div>
      <div><small>Execution</small><code>{m.run}</code></div>
      <div><small>Fit limit</small><span>{m.fitRows}</span></div>
      <Status tone="green">Succeeded · recorded</Status></div>)}</div>
    <div className="inline-action"><div><strong>New training can create billable Processing jobs.</strong>
      <span>Review the model and pipeline before opening the manual workflow.</span></div>
      <button className="button button-primary" onClick={() => openAction("training", path === "lstm" ? "lstm" : "rf")}>
        {icon(Play, 17, "fill")} Start training</button></div>
    <SourceFooter href={REPO + "/blob/master/docs/aws-deployment-status.md"} label="AWS deployment record" />
  </>;
}

function ModelReviewView({ selectedModel, selectModel, openAction }) {
  const model = MODELS.find(m => m.id === selectedModel) || MODELS[1];
  return <><SectionHeading eyebrow="RELEASE DECISION" title="Model review"
    description="Compare official-test evidence, then review a specific package before approval."
    aside={<Snapshot />} />
    <ModelTable selectedModel={selectedModel} selectModel={selectModel} navigate={() => {}} />
    <UnitNote /><div className="two-column review-details">
      <section className="detail-section"><div className="eyebrow">SELECTED MODEL</div>
        <h2>{model.name} <span className="subtle">{model.fullName}</span></h2>
        <FactRows rows={[["Official-test F1", model.f1.toFixed(6) + " · " + model.unit],
          ["Accuracy / FPR", model.accuracy.toFixed(6) + " / " + model.fpr.toFixed(6)],
          ["Training / test", model.fitRows + " / " + model.testRows],
          ["Approved package", model.package], ["Inference input", model.input]]} /></section>
      <section className="detail-section attention-section"><div className="eyebrow">NEEDS A RELEASE DECISION</div>
        <h2>SVM package v5</h2><p>The separate GitHub-started SVM run succeeded and registered
          <code> bigdata-ids-dev-classical/5</code> as <strong>PendingManualApproval</strong>.
          It has not replaced a serving endpoint.</p>
        <FactRows rows={[["Run", "c5kl0f3eaypx"], ["Review", "Evaluation, artifact and input contract"]]} />
        <button className="button button-primary" onClick={() => openAction("approval")}>
          {icon(ClipboardText, 18)} Review pending package</button></section></div>
    <SourceFooter href={REPO + "/blob/master/docs/aws-deployment-status.md"} label="AWS deployment record" />
  </>;
}

function ServingView({ openAction }) {
  return <><SectionHeading eyebrow="SERVERLESS INFERENCE" title="Serving endpoints"
    description="An approved package can exist without an endpoint. Current status is not connected."
    aside={<Snapshot />} />
    <div className="run-list">{MODELS.map(m => <div className="run-row" key={m.id}>
      <div><strong>{m.name}</strong><span>{m.package}</span></div>
      <div><small>Endpoint</small><span>{m.endpoint || "No dedicated endpoint"}</span></div>
      <div><small>Input</small><span>{m.input}</span></div>
      <Status tone={m.endpoint ? "green" : "neutral"}>
        {m.endpoint ? "InService · recorded" : "Not deployed"}</Status></div>)}</div>
    <div className="two-column serving-details">
      <section className="detail-section"><h2>Classical inference</h2>
        <p>RF and XGBoost accept one JSON record with 41 raw NSL-KDD fields. The packaged
          preprocessor creates 25 selected features.</p><code>{"{\"record\": { ...41 raw fields... }}"}</code></section>
      <section className="detail-section"><h2>LSTM inference</h2>
        <p>TensorFlow Serving expects a preprocessed 20 × 25 tensor. The recorded endpoint
          sometimes returned a no-response ModelError; one smoke test does not prove reliability.</p>
        <code>{"{\"instances\": [ ...20 × 25 tensor... ]}"}</code></section></div>
    <div className="inline-action"><div><strong>Deploy an approved package to a candidate endpoint.</strong>
      <span>The repository script does not replace an existing endpoint using another config.</span></div>
      <button className="button button-primary" onClick={() => openAction("deployment")}>
        {icon(Cloud, 18)} Review deployment</button></div>
    <SourceFooter href={REPO + "/blob/master/docs/OPERATIONS_RUNBOOK.md"} label="Operations runbook" />
  </>;
}

function MonitoringView() {
  return <><SectionHeading eyebrow="DRIFT EVIDENCE" title="Monitoring needs freshness context"
    description="Recorded PSI samples demonstrate an alarm; they are not a scheduled production monitor."
    aside={<Snapshot />} />
    <div className="notice warning-notice">{icon(WarningCircle, 23)}<span>
      <strong>An OK alarm state alone does not prove a fresh healthy measurement.</strong>
      Missing data is treated as non-breaching. Check the last datapoint.</span></div>
    <div className="drift-grid">
      {[["STABLE SAMPLE", "0.006151", "Recorded PSI demonstration"],
        ["SYNTHETIC SHIFT", "20.649132", "Deliberately shifted feature; not an intrusion"],
        ["OFFICIAL TEST", "0.251246", "Recorded PSI for KDDTest+"]].map(([name, value, note]) =>
        <div className="drift-item" key={name}><div className="eyebrow">{name}</div>
          <strong>{value}</strong><p>{note}</p></div>)}</div>
    <div className="two-column">
      <section className="detail-section"><h2>CloudWatch alarm</h2>
        <FactRows rows={[["Metric", "Capstone/IDS · MaxPSI"],
          ["Threshold", "> 0.25, 5-minute period"],
          ["Recorded event", "ALARM on synthetic shift"],
          ["Current observation", "Not connected"]]} /></section>
      <section className="detail-section"><h2>What is not automated</h2>
        <p>No scheduled drift job, SNS/email notification or SageMaker Model Monitor is configured.
          The existing Streamlit dashboard reads local JSON reports.</p>
        <ExternalLink href={CLOUDWATCH_CONSOLE}>Open CloudWatch</ExternalLink></section></div>
    <SourceFooter href={REPO + "/blob/master/docs/aws-deployment-status.md"} label="AWS deployment record" />
  </>;
}

function SourceFooter({ href, label }) {
  return <div className="source-footer">Source: <ExternalLink href={href}>{label}</ExternalLink>
    <span> · checked {SNAPSHOT_DATE}</span></div>;
}

function Guidance({ tab, navigate, openAction }) {
  const g = STAGE_GUIDANCE[tab];
  const detailLink = {
    Overview: [SAGEMAKER_CONSOLE, "Open SageMaker details"],
    Data: ["https://console.aws.amazon.com/s3/buckets?region=" + REGION, "Open S3 data"],
    Experiments: [REPO + "/blob/master/src/train_mlflow.py", "Open local training code"],
    Training: [SAGEMAKER_CONSOLE, "Open SageMaker pipelines"],
    "Model review": [SAGEMAKER_CONSOLE, "Open SageMaker details"],
    Serving: [SAGEMAKER_CONSOLE, "Open SageMaker endpoints"],
    Monitoring: [CLOUDWATCH_CONSOLE, "Open CloudWatch details"],
  }[tab];
  return <aside className="guidance" aria-label="Summary and guidance"><div className="guidance-inner">
    <h2>Summary &amp; guidance</h2><div className="eyebrow">{g.eyebrow}</div>
    <p className="guide-intro">{g.intro}</p>
    {[["What this shows", ClipboardText, g.shows], ["What to check", Info, g.checks]].map(
      ([title, Icon, list]) => <div className="guide-section" key={title}>
        <span className="guide-icon">{icon(Icon, 24)}</span><div><h3>{title}</h3>
          <ul>{list.map(item => <li key={item}>{item}</li>)}</ul></div></div>)}
    <div className="guide-section next-section"><span className="guide-icon">
      {icon(ArrowRight, 25)}</span><div><h3>Next step</h3><p>{g.next}</p></div></div>
    <button className="button button-primary guide-button"
      onClick={() => g.action ? openAction(g.action)
        : g.destination === tab ? document.querySelector(".drift-grid")?.scrollIntoView({ behavior: "smooth" })
        : navigate(g.destination)}>
      {icon(g.action === "training" ? Play : ClipboardText, 18)} {g.button}
      {icon(ArrowRight, 18)}</button>
    <div className="rail-permission">{icon(LockKey, 16)}
      AWS writes require separate authorization and confirmation</div>
    <div className="release-steps"><h3>Controlled release sequence</h3>
      <div><span>1</span> Start training</div><div><span>2</span> Approve exact package</div>
      <div><span>3</span> Deploy candidate endpoint</div></div>
    <ExternalLink href={detailLink[0]}>{detailLink[1]}</ExternalLink>
  </div></aside>;
}

function ActionModal({ action, initialModelId, onClose, notify }) {
  const [modelId, setModelId] = useState(initialModelId);
  const [candidate, setCandidate] = useState("bigdata-ids-dev-svm-candidate");
  const [checked, setChecked] = useState(false);
  const [prepared, setPrepared] = useState(false);
  const model = MODELS.find(m => m.id === modelId) || MODELS[0];
  useEffect(() => {
    const escape = e => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [onClose]);
  const title = { training: "Review training run", approval: "Review SVM package v5",
    deployment: "Review candidate deployment" }[action];
  const packageName = action === "approval" ? "bigdata-ids-dev-classical/5" : model.package;
  const arn = "arn:aws:sagemaker:" + REGION + ":101728439989:model-package/" + packageName;
  const command = action === "approval"
    ? "aws sagemaker update-model-package --model-package-arn " + arn
      + " --model-approval-status Approved --profile default --region " + REGION
    : "python scripts/deploy-endpoint.py --profile default --allow-root --package-arn "
      + arn + " --endpoint-name " + candidate + " --memory-mb "
      + (modelId === "lstm" ? "3072" : "2048") + " --max-concurrency 1 --wait";
  async function copy() {
    try { await navigator.clipboard.writeText(command);
      notify("Command copied. Review current AWS state before running it."); }
    catch { notify("Clipboard unavailable. Select the command text to copy it."); }
  }
  return <div className="modal-backdrop" onMouseDown={e => {
    if (e.target === e.currentTarget) onClose();
  }}><div className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
    <div className="modal-head"><div><div className="eyebrow">PROTOTYPE · NO AWS CONNECTION</div>
      <h2 id="modal-title">{title}</h2></div>
      <button className="icon-button" aria-label="Close dialog" onClick={onClose}>{icon(X, 22)}</button></div>
    {!prepared ? <>
      <p className="modal-intro">{action === "training"
        ? "Choose the model and inspect the target before continuing to the manual GitHub workflow."
        : action === "approval"
        ? "Approval applies to one registry package. It does not deploy or change an endpoint."
        : "Prepare a new candidate endpoint. The script will not switch an existing endpoint."}</p>
      {action !== "approval" && <label className="field-label">
        {action === "training" ? "Model to train" : "Approved package"}
        <select value={modelId} onChange={e => {
          setModelId(e.target.value); setChecked(false);
          if (action === "deployment") setCandidate("bigdata-ids-dev-" + e.target.value + "-candidate");
        }}>{MODELS.map(m => <option value={m.id} key={m.id}>{m.fullName} ({m.name})</option>)}</select>
      </label>}
      {action === "deployment" && <label className="field-label">New endpoint name
        <input value={candidate} onChange={e => { setCandidate(e.target.value); setChecked(false); }} />
      </label>}
      <FactRows rows={[["AWS account / Region", "101728439989 / " + REGION],
        [action === "training" ? "Pipeline" : "Model package",
          action === "training" ? model.pipeline : packageName],
        ["Recorded evidence", action === "approval" ? "SVM run c5kl0f3eaypx · PendingManualApproval"
          : action === "training" ? model.fitRows + " fit limit · " + model.unit
          : model.approval + " on " + SNAPSHOT_DATE]]} />
      <div className="notice warning-notice modal-warning">{icon(WarningCircle, 20)}
        <span>{action === "training" ? "Starting a run can create billable SageMaker Processing jobs."
          : action === "approval" ? "Check evaluation JSON, artifact and input contract before approving."
          : "A Serverless candidate may incur charges. Verify package and endpoint name."}</span></div>
      <label className="confirm-check"><input type="checkbox" checked={checked}
        onChange={e => setChecked(e.target.checked)} />
        <span>I reviewed the exact target and consequences above.</span></label>
      <div className="modal-actions"><button className="button button-secondary" onClick={onClose}>Cancel</button>
        <button className="button button-primary"
          disabled={!checked || (action === "deployment" && !/^[A-Za-z0-9-]+$/.test(candidate))}
          onClick={() => setPrepared(true)}>Continue to instructions {icon(ArrowRight, 17)}</button></div>
    </> : <><div className="prepared-icon">{icon(Check, 27)}</div>
      <h3>Review complete in this prototype</h3>
      <p className="modal-intro">No AWS change was made. Check current state and permissions before using
        the workflow or command outside this prototype.</p>
      {action === "training" ? <><div className="instruction-block">
        <strong>Manual GitHub workflow</strong><ol><li>Open the workflow on <code>master</code>.</li>
          <li>Select <strong>{model.name}</strong> and set <code>start_training=true</code>.</li>
          <li>Inspect the SageMaker execution before approval.</li></ol></div>
        <ExternalLink href={GITHUB_WORKFLOW} className="button button-primary modal-link">
          Open training workflow</ExternalLink></>
        : <><pre className="command-block">{command}</pre>
          <button className="button button-primary" onClick={copy}>{icon(Copy, 17)} Copy reviewed command</button></>}
      <div className="modal-actions"><button className="button button-secondary" onClick={onClose}>Done</button></div>
    </>}
  </div></div>;
}

export function App() {
  const [tab, setTab] = useState("Overview");
  const [selectedModel, selectModel] = useState("svm");
  const [action, setAction] = useState(null);
  const [modalModelId, setModalModelId] = useState("rf");
  const [toast, setToast] = useState("");
  useEffect(() => { if (!toast) return; const id = setTimeout(() => setToast(""), 4200);
    return () => clearTimeout(id); }, [toast]);
  const navigate = next => { setTab(next); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const openAction = (kind, modelId) => {
    setModalModelId(modelId || (kind === "deployment" ? "svm" : "rf"));
    setAction(kind);
  };
  return <div className="app-shell"><header className="topbar"><div className="brand">
    <span className="brand-mark"><img src="/assets/brand-mark.png" alt="" /></span>
    <strong>ML-IDS</strong><span className="brand-subtitle">Zero Trust Cloud</span>
    <span className="brand-divider" /><span className="brand-context">Intrusion detection</span>
  </div><div className="topbar-meta"><span>29 Sep 2026</span><span className="topbar-divider" />
    <span className="prototype-badge">Prototype · historical data</span></div></header>
    <nav className="top-nav" aria-label="Pipeline sections">{NAV_ITEMS.map(item =>
      <button key={item} className={tab === item ? "active" : ""}
        aria-current={tab === item ? "page" : undefined} onClick={() => navigate(item)}>{item}</button>)}</nav>
    <div className="workspace"><main className="main-content" id="main-content">
      {tab === "Overview" && <Overview navigate={navigate} selectedModel={selectedModel} selectModel={selectModel} />}
      {tab === "Data" && <DataView navigate={navigate} />}
      {tab === "Experiments" && <ExperimentsView navigate={navigate} />}
      {tab === "Training" && <TrainingView openAction={openAction} />}
      {tab === "Model review" && <ModelReviewView selectedModel={selectedModel}
        selectModel={selectModel} openAction={openAction} />}
      {tab === "Serving" && <ServingView openAction={openAction} />}
      {tab === "Monitoring" && <MonitoringView />}
    </main><Guidance tab={tab} navigate={navigate} openAction={openAction} /></div>
    {action && <ActionModal key={action + modalModelId} action={action}
      initialModelId={modalModelId} onClose={() => setAction(null)} notify={setToast} />}
    {toast && <div className="toast" role="status">{toast}</div>}
  </div>;
}
