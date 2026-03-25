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

Set `NEXT_PUBLIC_API_BASE_URL` (defaults to `http://127.0.0.1:8000`).

The UI calls:
- `POST /runs/weekly`
- `GET /runs/{runId}`
