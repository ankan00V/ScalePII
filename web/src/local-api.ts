const localSummary = {
  artifactUrl:
    'https://github.com/ankan00V/ScalePII/raw/main/output/Red%20Herring%20Prospectus%20-%20REDACTED.docx',
  githubUrl: 'https://github.com/ankan00V/ScalePII',
  metrics: [
    { label: 'Held-out F1', value: '0.9855', detail: 'Span-level, secondary annotations' },
    { label: 'Coverage F1', value: '1.0000', detail: 'Coverage-focused sample' },
    { label: 'Unit tests', value: '40', detail: 'Synthetic and DOCX edge cases' },
  ],
  verification: [
    { label: 'Visible occurrences checked', value: '610' },
    { label: 'Hidden field occurrences checked', value: '77' },
    { label: 'Embedded images neutralized', value: '8' },
  ],
};

/** Local build adapter only. The deployed app resolves @appdeploy/client. */
export const api = {
  get: async () => ({ data: localSummary }),
};
