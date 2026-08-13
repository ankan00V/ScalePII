# ScalePII Reviewer Console

This is a static Vite reviewer console for the ScalePII assignment. It links to
the redacted DOCX and public repository, and renders the committed evaluation
and delivery-verification evidence.

The interactive redaction walkthrough uses synthetic fixture data only. It lets
a reviewer inspect source highlighting, stable replacements and hash-only audit
records without exposing or transmitting the supplied prospectus.

It deliberately has no file-upload form, backend, database, authentication or
environment variables. The sensitive source prospectus continues to be
processed locally by the Python tool in the repository root.

## Deploy on Vercel

1. In Vercel, select **Add New → Project** and import
   `ankan00V/ScalePII` from GitHub.
2. Set **Root Directory** to `web`.
3. Confirm the detected framework is **Vite**.
4. Keep the default build settings:
   - Build Command: `npm run build`
   - Output Directory: `dist`
   - Install Command: `npm install`
5. Do not configure environment variables or a database.
6. Select **Deploy**.

Vercel will create preview deployments for pull requests and update production
after pushes to `main`. The suggested Vercel project name is
`scalepii-reviewer-console`.

## Local check

```bash
cd web
npm install
npm run build
npm run dev
```
