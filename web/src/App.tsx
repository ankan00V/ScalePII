import { useState } from 'react';
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  FileSearch,
  FileText,
  Github,
  LayoutDashboard,
  LockKeyhole,
  ScanLine,
  ShieldCheck,
  TerminalSquare,
} from 'lucide-react';

type PreviewTab = 'source' | 'redacted' | 'audit';

const projectSummary = {
  artifactUrl:
    'https://github.com/ankan00V/ScalePII/raw/main/output/Red%20Herring%20Prospectus%20-%20REDACTED.docx',
  githubUrl: 'https://github.com/ankan00V/ScalePII',
  metrics: [
    { label: 'Relaxed F1', value: '0.9855', detail: 'Secondary annotation set' },
    { label: 'Recall', value: '1.0000', detail: 'Secondary annotation set' },
    { label: 'Tests', value: '40', detail: 'Synthetic + DOCX edge cases' },
  ],
  verification: [
    { value: '610', label: 'visible replacements', detail: 'Text-layer occurrences checked' },
    { value: '77', label: 'hidden field values', detail: 'HYPERLINK field instructions checked' },
    { value: '8', label: 'image parts', detail: 'Raster assets neutralised' },
  ],
};

const coverage = ['People', 'Organisations', 'Email', 'Phone', 'Address', 'DIN', 'Website', 'Images'];

const auditRows = [
  { kind: 'PERSON', detector: 'gazetteer', hash: '1f0e…4d9a', replacement: 'Arjun Shah' },
  { kind: 'EMAIL', detector: 'regex:email', hash: '4b3a…7f2c', replacement: 'arjun.shah@example.org' },
  { kind: 'PHONE', detector: 'regex:phone', hash: '8c77…12ef', replacement: '+91 90741 68250' },
  { kind: 'ADDRESS', detector: 'context:address', hash: 'd4a9…c013', replacement: '18 Lake View Road, Example City' },
];

function PreviewContent({ tab }: { tab: PreviewTab }) {
  if (tab === 'audit') {
    return (
      <div className="audit-list" aria-label="Synthetic audit trace">
        <div className="audit-head"><span>TYPE</span><span>DETECTOR</span><span>SOURCE HASH</span><span>REPLACEMENT</span></div>
        {auditRows.map((row) => (
          <div className="audit-row" key={row.hash}>
            <span className={`type-pill type-${row.kind.toLowerCase()}`}>{row.kind}</span>
            <code>{row.detector}</code>
            <code>{row.hash}</code>
            <strong>{row.replacement}</strong>
          </div>
        ))}
      </div>
    );
  }

  const source = tab === 'source';
  return (
    <article className="document-sheet" aria-label={source ? 'Synthetic source example' : 'Synthetic redacted example'}>
      <div className="sheet-topline"><span>PROSPECTUS EXCERPT</span><span>PAGE 01</span></div>
      <h3>Compliance contact</h3>
      <p>
        For enquiries, contact{' '}
        <mark className={source ? 'source-token person' : 'redacted-token'}>{source ? 'Rohan Mehta' : 'Arjun Shah'}</mark>,
        Compliance Officer, at{' '}
        <mark className={source ? 'source-token email' : 'redacted-token'}>{source ? 'rohan.mehta@acme.example.com' : 'arjun.shah@example.org'}</mark>{' '}
        or <mark className={source ? 'source-token phone' : 'redacted-token'}>{source ? '+91 98765 43210' : '+91 90741 68250'}</mark>.
      </p>
      <p>
        The registered office is{' '}
        <mark className={source ? 'source-token address' : 'redacted-token'}>{source ? '42 Orchard Road, Example City 560001' : '18 Lake View Road, Example City 560001'}</mark>.
      </p>
      <div className="sheet-footnote">
        <span>{source ? 'Detected values are highlighted' : 'Stable fake alternatives are shown'}</span>
        <span>Illustrative fixture</span>
      </div>
    </article>
  );
}

function App() {
  const [previewTab, setPreviewTab] = useState<PreviewTab>('source');
  const [showWorkflow, setShowWorkflow] = useState(false);

  return (
    <main className="app-frame">
      <aside className="sidebar" aria-label="Project navigation">
        <a className="sidebar-brand" href="#overview" aria-label="ScalePII overview">
          <span className="brand-glyph"><ShieldCheck size={18} /></span>
          <span><strong>ScalePII</strong><small>PII REDACTION</small></span>
        </a>

        <nav className="side-nav">
          <a className="side-link active" href="#overview"><LayoutDashboard size={17} /> Overview</a>
          <a className="side-link" href="#preview"><FileSearch size={17} /> Redaction preview</a>
          <a className="side-link" href="#verification"><ClipboardCheck size={17} /> Verification</a>
          <a className="side-link" href={`${projectSummary.githubUrl}/blob/main/EVALUATION.md`} target="_blank" rel="noreferrer"><FileText size={17} /> Evaluation <ArrowUpRight size={13} /></a>
        </nav>

        <div className="sidebar-spacer" />
        <div className="local-only">
          <span className="local-icon"><LockKeyhole size={15} /></span>
          <div><strong>Local-only processing</strong><p>Source files are not uploaded here.</p></div>
        </div>
        <a className="repository-link" href={projectSummary.githubUrl} target="_blank" rel="noreferrer"><Github size={16} /> View repository <ArrowUpRight size={13} /></a>
      </aside>

      <section className="workspace" id="overview">
        <header className="topbar">
          <div className="crumbs"><span>Assignments</span><ArrowRight size={13} /><strong>Red Herring Prospectus</strong></div>
          <div className="topbar-actions">
            <span className="verified-badge"><i /><span>Verified delivery</span></span>
            <a href={projectSummary.githubUrl} target="_blank" rel="noreferrer"><Github size={17} /></a>
          </div>
        </header>

        <div className="content-wrap">
          <section className="page-intro">
            <div>
              <p className="eyebrow">ASSIGNMENT DELIVERY</p>
              <h1>Review the redaction,<br /><span>not just the result.</span></h1>
              <p className="intro-copy">A deterministic DOCX pipeline with a verifiable output package, privacy-safe audit artefacts and documented evaluation methodology.</p>
            </div>
            <a className="primary-download" href={projectSummary.artifactUrl}><ArrowDownToLine size={18} /> Download final DOCX</a>
          </section>

          <section className="run-overview" aria-label="Final redaction run summary">
            <article className="run-card document-run">
              <div className="run-card-header"><span className="card-kicker">FINAL RUN</span><span className="success-chip"><Check size={13} /> COMPLETE</span></div>
              <div className="file-row">
                <span className="file-icon"><FileText size={22} /></span>
                <div><h2>Red Herring Prospectus</h2><p>Output package · DOCX · privacy-safe audit attached</p></div>
                <a href={projectSummary.artifactUrl} aria-label="Download redacted document"><ArrowDownToLine size={19} /></a>
              </div>
              <div className="pipeline-track" aria-label="Pipeline stages">
                <div className="track-step"><span><Check size={12} /></span><p>Parse DOCX</p></div>
                <i />
                <div className="track-step"><span><Check size={12} /></span><p>Detect PII</p></div>
                <i />
                <div className="track-step"><span><Check size={12} /></span><p>Replace + audit</p></div>
                <i />
                <div className="track-step"><span><Check size={12} /></span><p>Verify package</p></div>
              </div>
            </article>

            <article className="run-card scope-card">
              <div className="run-card-header"><span className="card-kicker">POLICY COVERAGE</span><span className="count-label">8 TYPES</span></div>
              <h2>Detection scope</h2>
              <div className="scope-list">{coverage.map((item) => <span key={item}>{item}</span>)}</div>
              <p className="scope-note">SSN, card, DOB and IP detectors are exercised in tests; no matches were present in this text layer.</p>
            </article>
          </section>

          <section className="preview-panel" id="preview" aria-labelledby="preview-heading">
            <div className="panel-intro">
              <div><p className="eyebrow">INTERACTIVE WALKTHROUGH</p><h2 id="preview-heading">Inspect a transformation.</h2></div>
              <p>This is a synthetic, client-side fixture—never the submitted prospectus. It shows how the same pipeline represents source values, replacements and audit records.</p>
            </div>

            <div className="preview-workbench">
              <div className="preview-nav" role="tablist" aria-label="Transformation views">
                <button className={previewTab === 'source' ? 'selected' : ''} onClick={() => setPreviewTab('source')} role="tab" aria-selected={previewTab === 'source'}>01 <span>Source view</span></button>
                <button className={previewTab === 'redacted' ? 'selected' : ''} onClick={() => setPreviewTab('redacted')} role="tab" aria-selected={previewTab === 'redacted'}>02 <span>Redacted output</span></button>
                <button className={previewTab === 'audit' ? 'selected' : ''} onClick={() => setPreviewTab('audit')} role="tab" aria-selected={previewTab === 'audit'}>03 <span>Audit trace</span></button>
                <div className="preview-status"><ScanLine size={15} /><span>STATIC DEMO</span></div>
              </div>
              <div className="preview-stage"><PreviewContent tab={previewTab} /></div>
              <aside className="preview-aside">
                <p className="card-kicker">WHAT CHANGES</p>
                <h3>{previewTab === 'source' ? 'Detectors locate values across Word runs.' : previewTab === 'redacted' ? 'One source value maps to one stable fake.' : 'Audits preserve provenance without source PII.'}</h3>
                <p>{previewTab === 'source' ? 'Contextual and deterministic detectors resolve overlaps before any text is altered.' : previewTab === 'redacted' ? 'The mapped replacement is plausible, memoised and format-aware—not a generic redaction token.' : 'Mappings store a SHA-256 fingerprint for the source value plus the replacement and entity type.'}</p>
                <a href={`${projectSummary.githubUrl}/blob/main/REVIEWER_GUIDE.md`} target="_blank" rel="noreferrer">Read reviewer guide <ArrowUpRight size={14} /></a>
              </aside>
            </div>
          </section>

          <section className="evidence-grid" id="verification" aria-labelledby="evidence-heading">
            <article className="evidence-summary">
              <p className="eyebrow">PACKAGE VERIFICATION</p>
              <h2 id="evidence-heading">The DOCX was checked below the visible layer.</h2>
              <p>The verifier opens the serialised Word package and tests structure, detected text values, hidden field instructions and embedded media.</p>
              <a href={`${projectSummary.githubUrl}/blob/main/verify_delivery.py`} target="_blank" rel="noreferrer">Open verifier <ArrowUpRight size={15} /></a>
            </article>
            <div className="verification-table">
              {projectSummary.verification.map((item) => (
                <div className="verification-row" key={item.label}>
                  <span className="check-square"><CheckCircle2 size={17} /></span>
                  <div><strong>{item.value}</strong><p>{item.label}</p></div>
                  <small>{item.detail}</small>
                </div>
              ))}
            </div>
          </section>

          <section className="evaluation-strip" aria-label="Evaluation summary">
            <div className="evaluation-copy"><p className="eyebrow">EVALUATION SNAPSHOT</p><h2>Measured on saved annotations.</h2><p>Metrics are reported with sampling and limitation details, not as an unbounded real-world claim.</p></div>
            <div className="metric-group">
              {projectSummary.metrics.map((metric) => <div key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong><small>{metric.detail}</small></div>)}
            </div>
          </section>

          <section className="privacy-boundary">
            <div className="boundary-symbol"><LockKeyhole size={21} /></div>
            <div><h2>Privacy boundary by design.</h2><p>No source document, annotation set or credential is collected by this site. The submitted artefacts are read-only; exact processing happens locally.</p></div>
            <div className="workflow-toggle">
              <button type="button" onClick={() => setShowWorkflow((visible) => !visible)} aria-expanded={showWorkflow}><span>{showWorkflow ? 'Hide' : 'Show'} local command</span><ChevronDown size={17} /></button>
              {showWorkflow && <pre><TerminalSquare size={15} /> python redact.py --input input.docx --output output/redacted.docx</pre>}
            </div>
          </section>
        </div>

        <footer className="workspace-footer"><span>ScalePII · DOCX PII Redaction Tool</span><span>Prepared for technical review</span></footer>
      </section>
    </main>
  );
}

export default App;
