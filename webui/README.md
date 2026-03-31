## Review Pulse Web UI (Next.js)

1. Install dependencies:

```bash
npm install
```

2. Start dev server:

```bash
npm run dev
```

3. Configure backend URL:

Set `NEXT_PUBLIC_API_BASE_URL` (defaults to `https://web-production-628ea.up.railway.app` in this repo).

The UI calls:
- `POST /runs/weekly`
- `GET /runs/{runId}`

## Deploy on Vercel

1. Import this GitHub repo in Vercel.
2. Set **Root Directory** to `webui`.
3. Add env var:
   - `NEXT_PUBLIC_API_BASE_URL=https://web-production-628ea.up.railway.app`
4. Deploy.

If backend CORS is restricted, set Railway variable:
- `REVIEW_PULSE_CORS_ORIGINS=https://<your-vercel-domain>.vercel.app`
