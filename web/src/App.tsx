import { useState } from 'react';
import {
  ArrowDownToLine,
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronDown,
  FileCheck2,
  FileSearch,
  FileText,
  Github,
  LockKeyhole,
  ScanLine,
  ShieldCheck,
  TerminalSquare,
  X,
} from 'lucide-react';

type PreviewTab = 'source' | 'redacted' | 'audit';

const project = {
  artifactUrl:
    'https://github.com/ankan00V/ScalePII/raw/main/output/Red%20Herring%20Prospectus%20-%20REDACTED.docx',
  evaluationUrl:
    'https://github.com/ankan00V/ScalePII/raw/main/output/PII_Redaction_Evaluation_Report.docx',
  githubUrl: 'https://github.com/ankan00V/ScalePII',
};

const requiredCoverage = [
  'Full names',
  'Email addresses',
  'Phone numbers',
  'Company names',
  'Mailing addresses',
  'SSNs',
  'Card numbers',
  'Dates of birth',
  'IP addresses',
];

const auditRows = [
  { kind: 'PERSON', detector: 'gazetteer', hash: '1f0e…4d9a', replacement: 'Arjun Shah' },
  { kind: 'ORG', detector: 'NER + gazetteer', hash: '90cd…85ae', replacement: 'Northstar Disclosure Services Pvt. Ltd.' },
  { kind: 'EMAIL', detector: 'regex:email', hash: '4b3a…7f2c', replacement: 'arjun.shah@example.org' },
  { kind: 'PHONE', detector: 'regex:phone', hash: '8c77…12ef', replacement: '+91 90741 68250' },
  { kind: 'ADDRESS', detector: 'context:address', hash: 'd4a9…c013', replacement: '18 Lake View Road, Example City' },
];

function SyntheticDocument({ tab }: { tab: PreviewTab }) {
  if (tab === 'audit') {
    return (
      <div className="audit-table" aria-label="Synthetic audit trace">
        <div className="audit-table-head"><span>TYPE</span><span>DETECTOR</span><span>SOURCE HASH</span><span>FAKE VALUE</span></div>
        {auditRows.map((row) => (
          <div className="audit-table-row" key={row.hash}>
            <span className={`audit-type ${row.kind.toLowerCase()}`}>{row.kind}</span>
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
    <article className="sample-page" aria-label={source ? 'Synthetic source example' : 'Synthetic redacted example'}>
      <div className="sample-page-meta"><span>PROSPECTUS EXCERPT</span><span>FIXTURE / 01</span></div>
      <h3>Compliance contact</h3>
      <p>
        For enquiries at{' '}
        <mark className={source ? 'sample-token org' : 'fake-token'}>{source ? 'Acme Prospectus Services Pvt. Ltd.' : 'Northstar Disclosure Services Pvt. Ltd.'}</mark>, contact{' '}
        <mark className={source ? 'sample-token person' : 'fake-token'}>{source ? 'Rohan Mehta' : 'Arjun Shah'}</mark>,
        Compliance Officer, at{' '}
        <mark className={source ? 'sample-token email' : 'fake-token'}>{source ? 'rohan.mehta@acme.example.com' : 'arjun.shah@example.org'}</mark>{' '}
        or <mark className={source ? 'sample-token phone' : 'fake-token'}>{source ? '+91 98765 43210' : '+91 90741 68250'}</mark>.
      </p>
      <p>
        The registered office is{' '}
        <mark className={source ? 'sample-token address' : 'fake-token'}>{source ? '42 Orchard Road, Example City 560001' : '18 Lake View Road, Example City 560001'}</mark>.
      </p>
      <div className="sample-page-foot"><span>{source ? 'Detected values highlighted' : 'Stable fake alternatives applied'}</span><span>FICTIONAL DATA</span></div>
    </article>
  );
}

function BrowserPanel() {
  const [tab, setTab] = useState<PreviewTab>('source');

  const tabCopy = {
    source: { title: 'Locate the sensitive value.', text: 'Detectors resolve cross-run text before anything changes.' },
    redacted: { title: 'Apply one believable fake.', text: 'Memoised mappings keep a source value consistent throughout a run.' },
    audit: { title: 'Leave a safe trace.', text: 'The audit stores a source hash, detector and replacement—not raw PII.' },
  }[tab];

  return (
    <div className="browser-shell">
      <div className="browser-topline"><span className="traffic-lights"><i /><i /><i /></span><span>scalepii.local / inspection</span><span className="browser-status">LOCAL-ONLY</span></div>
      <div className="browser-body">
        <div className="browser-side">
          <p>SAFE WALKTHROUGH</p>
          {(['source', 'redacted', 'audit'] as PreviewTab[]).map((item, index) => (
            <button key={item} className={tab === item ? 'selected' : ''} onClick={() => setTab(item)} type="button" aria-pressed={tab === item}>
              <b>0{index + 1}</b><span>{item === 'source' ? 'Source values' : item === 'redacted' ? 'Fake values' : 'Audit trace'}</span>
            </button>
          ))}
          <div className="browser-side-note"><LockKeyhole size={14} /> Never the submitted prospectus.</div>
        </div>
        <div className="browser-canvas"><SyntheticDocument tab={tab} /></div>
        <aside className="browser-explainer">
          <span className="mini-label">WHAT THIS PROVES</span>
          <h3>{tabCopy.title}</h3>
          <p>{tabCopy.text}</p>
          <a href={`${project.githubUrl}/blob/main/REVIEWER_GUIDE.md`} target="_blank" rel="noreferrer">Read the reviewer guide <ArrowUpRight size={14} /></a>
        </aside>
      </div>
    </div>
  );
}

function App() {
  const [showCommand, setShowCommand] = useState(false);

  return (
    <main>
      <header className="top-nav">
        <a className="brand" href="#top" aria-label="ScalePII home"><span className="brand-mark"><ShieldCheck size={18} /></span><strong>ScalePII</strong></a>
        <nav aria-label="Page navigation"><a href="#delivery">Delivery</a><a href="#walkthrough">Walkthrough</a><a href="#evaluation">Evaluation</a></nav>
        <a className="nav-repo" href={project.githubUrl} target="_blank" rel="noreferrer"><Github size={17} /> View source</a>
      </header>

      <section className="hero" id="top">
        <div className="hero-grid">
          <div className="hero-copy">
            <h1>PII redaction<br />for a <span>real</span> DOCX.</h1>
            <p>This is the review surface for a local-first Word redaction pipeline: the output, evidence and trade-offs are all here to inspect.</p>
            <div className="hero-actions">
              <a className="push-button dark" href={project.artifactUrl}><ArrowDownToLine size={18} /> Get redacted DOCX</a>
              <a className="push-button light" href="#walkthrough"><FileSearch size={18} /> Inspect the proof</a>
            </div>
            <div className="hero-caption"><CheckCircle2 size={17} /> No upload form. No database. No source PII leaves the local workflow.</div>
          </div>

          <div className="run-window" aria-label="Verified delivery receipt">
            <div className="run-window-bar"><span>FINAL RUN / RECEIPT</span><span className="receipt-complete"><Check size={13} /> VERIFIED</span></div>
            <div className="run-window-file"><span className="file-stamp"><FileText size={25} /></span><div><strong>Red Herring Prospectus</strong><small>REDACTED DOCX · FINAL OUTPUT</small></div><FileCheck2 size={22} /></div>
            <div className="run-numbers">
              <div><b>610</b><span>visible replacements</span></div>
              <div><b>77</b><span>hidden field values</span></div>
              <div><b>8</b><span>image parts neutralised</span></div>
            </div>
            <div className="run-steps"><span><i><Check size={11} /></i> Parse</span><b /><span><i><Check size={11} /></i> Detect</span><b /><span><i><Check size={11} /></i> Replace</span><b /><span><i><Check size={11} /></i> Verify</span></div>
            <div className="run-window-bottom"><span><ScanLine size={15} /> 4,181 text blocks scanned</span><a href={`${project.githubUrl}/blob/main/reports/run_summary.json`} target="_blank" rel="noreferrer">Open run receipt <ArrowUpRight size={13} /></a></div>
          </div>
        </div>
      </section>

      <section className="evidence-ticker" aria-label="Verified run facts">
        <div><span>610 VISIBLE REPLACEMENTS</span><b>✦</b><span>77 HIDDEN WORD FIELDS</span><b>✦</b><span>8 IMAGE PARTS NEUTRALISED</span><b>✦</b><span>40 TESTS PASSING</span><b>✦</b><span>258 STABLE MAPPINGS</span></div>
      </section>

      <section className="delivery-section" id="delivery">
        <div className="section-heading"><span className="section-number">01</span><div><p>THE HANDOFF</p><h2>Built to be <em>inspected,</em><br />not merely demoed.</h2></div></div>
        <div className="delivery-grid">
          <article className="contrast-card problem-card"><span className="card-sign"><X size={17} /></span><p className="mini-label">THE WEAK VERSION</p><h3>“It redacted the file.”</h3><ul><li>A generic token removes document usefulness.</li><li>Visible text can hide a live mailto link.</li><li>An attractive score says little without a method.</li></ul></article>
          <article className="contrast-card proof-card"><span className="card-sign"><Check size={17} /></span><p className="mini-label">THIS DELIVERY</p><h3>“Here is the output and the proof.”</h3><ul><li>Stable, plausible fake alternatives preserve readability.</li><li>Serialized XML, hyperlinks and media are verified.</li><li>Evaluation records precision, recall and limitations.</li></ul><div className="artifact-links"><a href={project.artifactUrl}>Final DOCX <ArrowDownToLine size={15} /></a><a href={project.evaluationUrl}>Evaluation DOCX <ArrowDownToLine size={15} /></a></div></article>
        </div>
      </section>

      <section className="feature-section">
        <div className="feature-heading"><p>WHAT IS ACTUALLY IN THE TOOL</p><h2>Practical safeguards,<br /><span>not a black box.</span></h2></div>
        <div className="feature-grid">
          <article><span className="feature-icon"><FileSearch size={22} /></span><h3>Word-aware detection</h3><p>Text is flattened across styled runs, then mapped back into paragraphs, tables, headers, footers and fields.</p></article>
          <article><span className="feature-icon"><ShieldCheck size={22} /></span><h3>Format-aware fakes</h3><p>Seeded replacements are plausible, memoised and casing-aware instead of a repetitive [REDACTED] label.</p></article>
          <article><span className="feature-icon"><CheckCircle2 size={22} /></span><h3>Package-level checks</h3><p>The final DOCX package is checked below the visible layer for XML values, mailto targets and raster media.</p></article>
        </div>
      </section>

      <section className="walkthrough-section" id="walkthrough">
        <div className="walkthrough-heading"><div><p>02 / THE REVIEW LAB</p><h2>Trace one transformation<br /><span>without exposing the file.</span></h2></div><p>All values below are fictional. This browser-side fixture gives reviewers an honest way to explore the pipeline without transmitting the supplied prospectus.</p></div>
        <div className="walkthrough-flow"><span><b>1</b> Locate source value</span><i /><span><b>2</b> Generate stable fake</span><i /><span><b>3</b> Retain hash-only trace</span></div>
        <BrowserPanel />
      </section>

      <section className="coverage-section">
        <div className="coverage-copy"><p>03 / ASSIGNMENT BASELINE</p><h2>All nine required<br />PII categories.</h2><p>SSN, card, DOB and IP detectors returned no text-layer matches in this prospectus. Their end-to-end paths are covered by synthetic tests.</p><small>Extra protective coverage: DINs, websites, hidden Word links and embedded images.</small></div>
        <div className="coverage-grid">{requiredCoverage.map((item, index) => <div key={item}><span>0{index + 1}</span><strong>{item}</strong><Check size={16} /></div>)}</div>
      </section>

      <section className="evaluation-section" id="evaluation">
        <div className="evaluation-title"><p>04 / EVALUATION</p><h2>A score is useful<br />when it is qualified.</h2><p>The secondary annotation set is sampled by document position, excludes development blocks, and is reported with the known precision trade-off.</p><a href={project.evaluationUrl}>Open the evaluation report <ArrowDownToLine size={16} /></a></div>
        <div className="score-card"><div className="score-top"><span>SECONDARY ANNOTATION SET</span><b>130 BLOCKS</b></div><div className="score-grid"><div><small>RELAXED F1</small><strong>0.9855</strong></div><div><small>RECALL</small><strong>1.0000</strong></div><div><small>CHAR. ACCURACY</small><strong>0.9944</strong></div></div><p><CheckCircle2 size={16} /> 34 true positives · 1 false positive · 0 false negatives</p><a href={`${project.githubUrl}/blob/main/EVALUATION.md`} target="_blank" rel="noreferrer">Read methodology and limitations <ArrowUpRight size={14} /></a></div>
      </section>

      <section className="privacy-section">
        <div className="privacy-icon"><LockKeyhole size={26} /></div><div><p>SECURITY BOUNDARY</p><h2>The cloud page does not process the prospectus.</h2><span>No document, raw audit record, annotation set or credential is collected here. The tested pipeline runs locally, and the public console only links to the finished, privacy-safe artefacts.</span></div>
        <div className="command-wrap"><button type="button" onClick={() => setShowCommand((visible) => !visible)} aria-expanded={showCommand}>Show local command <ChevronDown size={17} /></button>{showCommand && <pre><TerminalSquare size={15} /> python redact.py --input input.docx --output output/redacted.docx</pre>}</div>
      </section>

      <footer><span><b>ScalePII</b></span><a href={project.githubUrl} target="_blank" rel="noreferrer">GitHub source <ArrowUpRight size={14} /></a></footer>
    </main>
  );
}

export default App;
