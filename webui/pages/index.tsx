import { useEffect, useState } from "react";

type RunStatus = {
  runId: string;
  status: string;
  phaseStatus?: Record<string, any>;
  error?: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export default function Home() {
  const [weekBucket, setWeekBucket] = useState("2026-W12");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [recipientName, setRecipientName] = useState("");
  const [sendNow, setSendNow] = useState(false);

  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("idle");
  const [lastError, setLastError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    const t = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/runs/${runId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as RunStatus;
        setStatus(data.status);
        setLastError(data.error || null);
        if (data.status === "succeeded" || data.status === "failed") {
          clearInterval(t);
        }
      } catch (e: any) {
        setLastError(e?.message || String(e));
        clearInterval(t);
      }
    }, 1500);
    return () => clearInterval(t);
  }, [runId]);

  async function startRun() {
    setRunId(null);
    setStatus("starting");
    setLastError(null);

    const body: any = {
      weekBucket,
      triggerType: "ui",
      recipientEmail: recipientEmail || null,
      recipientName: recipientName || null,
      sendNow,
      chunked: false,
      maxReviews: 500,
      maxChars: 80000,
    };

    const res = await fetch(`${API_BASE}/runs/weekly`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const detail = await res.text();
      setStatus("failed");
      setLastError(detail);
      return;
    }
    const data = await res.json();
    setRunId(data.runId);
    setStatus("running");
  }

  return (
    <div style={{ padding: 24, fontFamily: "system-ui, sans-serif" }}>
      <h1>Review Pulse</h1>
      <div style={{ display: "grid", gap: 12, maxWidth: 520 }}>
        <label>
          Week bucket
          <input value={weekBucket} onChange={(e) => setWeekBucket(e.target.value)} style={{ width: "100%" }} />
        </label>
        <label>
          Recipient email
          <input value={recipientEmail} onChange={(e) => setRecipientEmail(e.target.value)} style={{ width: "100%" }} />
        </label>
        <label>
          Recipient name
          <input value={recipientName} onChange={(e) => setRecipientName(e.target.value)} style={{ width: "100%" }} />
        </label>
        <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={sendNow} onChange={(e) => setSendNow(e.target.checked)} />
          Send immediately (gmail only in MVP)
        </label>
        <button onClick={startRun} style={{ padding: "10px 14px" }}>
          Generate & Create Draft
        </button>
        <div>
          <div>Run ID: {runId || "-"}</div>
          <div>Status: {status}</div>
          {lastError ? <pre style={{ color: "crimson" }}>{lastError}</pre> : null}
        </div>
      </div>
    </div>
  );
}

