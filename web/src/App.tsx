import { useState } from 'react';
import {
  ArrowDownToLine,
  ArrowUpRight,
  Check,
  ChevronDown,
  FileText,
  Fingerprint,
  Github,
  LockKeyhole,
  ScanLine,
  ShieldCheck,
  TerminalSquare,
} from 'lucide-react';

type Metric = {
  label: string;
  value: string;
  detail: string;
};

type Verification = {
  value: string;
  label: string;
  detail: string;
};

const projectSummary = {
  artifactUrl:
    'https://github.com/ankan00V/ScalePII/raw/main/output/Red%20Herring%20Prospectus%20-%20REDACTED.docx',
  githubUrl: 'https://github.com/ankan00V/ScalePII',
  metrics: [
    { label: 'Held-out F1', value: '0.9855', detail: 'Secondary annotation set' },
    { label: 'Coverage F1', value: '1.0000', detail: 'Coverage-focused sample' },
    { label: 'Regression tests', value: '40', detail: 'Synthetic + DOCX edge cases' },
  ] satisfies Metric[],
  verification: [
    {
      value: '610',
      label: 'visible replacements inspected',
      detail: 'Text-layer values detected by the current pipeline.',
    },
    {
      value: '77',
      label: 'hidden field values cleared',
      detail: 'Includes Word hyperlink instructions, not just visible text.',
    },
    {
      value: '8',
      label: 'image assets neutralised',
      detail: 'Fail-closed replacement for embedded raster media.',
    },
  ] satisfies Verification[],
};

const releaseFacts = [
  ['SOURCE', 'Red Herring Prospectus'],
  ['OUTPUT', 'Pseudonymised .docx'],
  ['MODE', 'Local processing'],
];

function App() {
  const [showBoundary, setShowBoundary] = useState(false);

  return (
    <main className="site-shell">
      <div className="paper-grid" aria-hidden="true" />

      <header className="masthead page-width">
        <a className="brand" href="#top" aria-label="ScalePII home">
          <span className="brand-mark">SP</span>
          <span className="brand-type">
            <strong>ScalePII</strong>
            <small>REVIEW CONSOLE / 01</small>
          </span>
        </a>

        <div className="masthead-meta">
          <span className="status-mark"><i /> DELIVERY VERIFIED</span>
          <a href={projectSummary.githubUrl} target="_blank" rel="noreferrer">
            Repository <ArrowUpRight size={15} />
          </a>
        </div>
      </header>

      <section className="hero page-width" id="top">
        <div className="hero-copy reveal">
          <p className="kicker"><span>01</span> Privacy redaction / assignment delivery</p>
          <h1>A redaction run<br />you can <em>interrogate.</em></h1>
          <p className="hero-intro">
            A reproducible DOCX pipeline that replaces sensitive values with stable fake alternatives, preserves document structure, and proves what it checked.
          </p>

          <div className="hero-actions">
            <a className="action action-primary" href={projectSummary.artifactUrl}>
              <ArrowDownToLine size={18} />
              <span>Download redacted DOCX</span>
            </a>
            <a className="action action-secondary" href={projectSummary.githubUrl} target="_blank" rel="noreferrer">
              <Github size={18} />
              <span>Review implementation</span>
            </a>
          </div>

          <dl className="run-facts" aria-label="Release facts">
            {releaseFacts.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </div>

        <article className="dossier reveal reveal-late" aria-label="Final delivery dossier">
          <div className="dossier-topline">
            <span>DELIVERY DOSSIER</span>
            <span>RHP / 01</span>
          </div>
          <div className="dossier-title">
            <span className="dossier-number">01</span>
            <div>
              <p>FINAL OUTPUT</p>
              <h2>Serialized package<br />verification</h2>
            </div>
          </div>
          <div className="redaction-sample" aria-hidden="true">
            <span className="line line-one" />
            <span className="line line-two" />
            <span className="line line-three" />
            <span className="line line-four" />
            <span className="line line-five" />
            <span className="redaction-bar" />
          </div>
          <div className="dossier-result">
            <span className="result-icon"><Check size={17} strokeWidth={3} /></span>
            <div>
              <strong>Package check passed</strong>
              <p>Structure, hidden fields and embedded media inspected.</p>
            </div>
          </div>
          <div className="dossier-footnote">
            <Fingerprint size={15} /> Audit records contain source hashes, never source text.
          </div>
        </article>
      </section>

      <section className="release-band" aria-label="Release status">
        <div className="page-width release-band-content">
          <span className="release-band-label"><ShieldCheck size={18} /> RELEASE POSTURE</span>
          <p>Source material remains local. The public artefacts contain the processed document and privacy-safe audit evidence only.</p>
          <a href="#evidence">Inspect evidence <ArrowUpRight size={15} /></a>
        </div>
      </section>

      <section className="page-width metrics-section" aria-labelledby="metrics-heading">
        <div className="section-label reveal">
          <span>02</span>
          <p>Evaluation snapshot</p>
        </div>
        <div className="section-heading reveal">
          <h2 id="metrics-heading">Numbers with<br />their caveats intact.</h2>
          <p>
            Scores are tied to saved annotations and documented methodology. They are evidence from this run—not a claim of universal coverage.
          </p>
        </div>
        <div className="metric-grid">
          {projectSummary.metrics.map((metric, index) => (
            <article className="metric-card reveal" style={{ '--delay': `${index * 80}ms` } as React.CSSProperties} key={metric.label}>
              <span className="metric-index">0{index + 1}</span>
              <p>{metric.label}</p>
              <strong>{metric.value}</strong>
              <small>{metric.detail}</small>
            </article>
          ))}
        </div>
        <a className="text-link" href={`${projectSummary.githubUrl}/blob/main/EVALUATION.md`} target="_blank" rel="noreferrer">
          Read evaluation strategy <ArrowUpRight size={16} />
        </a>
      </section>

      <section className="page-width evidence-section" id="evidence" aria-labelledby="evidence-heading">
        <div className="evidence-heading reveal">
          <div className="section-label">
            <span>03</span>
            <p>Delivery evidence</p>
          </div>
          <h2 id="evidence-heading">The verifier works beneath the surface.</h2>
          <p>
            Visual inspection is not enough for a Word package. The delivery verifier opens the final DOCX and checks the serialised content, not only what Word displays.
          </p>
        </div>

        <div className="evidence-ledger">
          {projectSummary.verification.map((item, index) => (
            <article className="ledger-row reveal" style={{ '--delay': `${index * 90}ms` } as React.CSSProperties} key={item.label}>
              <span className="ledger-index">0{index + 1}</span>
              <strong>{item.value}</strong>
              <div>
                <h3>{item.label}</h3>
                <p>{item.detail}</p>
              </div>
              <ScanLine className="ledger-icon" size={20} />
            </article>
          ))}
        </div>
      </section>

      <section className="page-width boundary-section reveal" aria-labelledby="boundary-heading">
        <div className="boundary-flag"><LockKeyhole size={21} /><span>PROCESSING BOUNDARY</span></div>
        <div className="boundary-copy">
          <h2 id="boundary-heading">No source documents<br />leave the review path.</h2>
          <p>
            This site deliberately has no upload form, database or account system. The provided prospectus and gold annotations remain local; the exact tested pipeline runs where the sensitive material belongs.
          </p>
        </div>
        <div className="boundary-action">
          <button type="button" onClick={() => setShowBoundary((visible) => !visible)} aria-expanded={showBoundary}>
            <span>{showBoundary ? 'Hide' : 'Show'} local workflow</span>
            <ChevronDown size={18} />
          </button>
          {showBoundary && (
            <pre><TerminalSquare size={16} /> python redact.py --input input.docx --output output/redacted.docx</pre>
          )}
        </div>
      </section>

      <footer className="footer page-width">
        <div>
          <strong>ScalePII</strong>
          <span>DOCX PII Redaction Tool</span>
        </div>
        <p>Evidence console · built for reviewer scrutiny</p>
        <a href={projectSummary.githubUrl} target="_blank" rel="noreferrer">GitHub <ArrowUpRight size={15} /></a>
      </footer>
    </main>
  );
}

export default App;
