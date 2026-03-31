import Head from "next/head";
import { useEffect, useMemo, useState } from "react";
import { dateToIsoWeek, eightWeeksEndingAt, formatIsoWeek } from "../lib/isoWeek";

type RunStatus = {
  runId: string;
  status: string;
  phaseStatus?: Record<string, unknown>;
  error?: string | null;
};

type ThemeRow = {
  name?: string;
  evidenceVolume?: number;
  reviewCount?: number;
};

type WeeklyReport = {
  week?: string;
  topThemes?: ThemeRow[];
  quotes?: unknown[];
  actionIdeas?: unknown[];
  noteText?: string;
  wordCount?: number;
};

type ActionRow = { theme_name?: string; idea?: string; effort?: string; impact?: string };

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "https://web-production-628ea.up.railway.app";

function statusPillClass(status: string): string {
  const s = status.toLowerCase();
  if (s === "succeeded") return "ra-pill ra-pill-succeeded";
  if (s === "failed") return "ra-pill ra-pill-failed";
  if (s === "running" || s === "starting") return "ra-pill ra-pill-running";
  return "ra-pill ra-pill-idle";
}

function themeVolume(t: ThemeRow): number {
  return t.evidenceVolume ?? t.reviewCount ?? 0;
}

function quoteText(q: unknown): string {
  if (typeof q === "string") return q;
  if (q && typeof q === "object" && "quote" in q) {
    const v = (q as { quote?: unknown }).quote;
    return typeof v === "string" ? v : "";
  }
  return "";
}

function asAction(a: unknown): ActionRow {
  if (a && typeof a === "object") return a as ActionRow;
  return {};
}

function priorityLabel(a: ActionRow): { text: string; className: string } {
  const imp = (a.impact || "").toUpperCase();
  const eff = (a.effort || "").toUpperCase();
  if (imp === "H" && eff === "S") return { text: "HIGH PRIORITY", className: "gw-priority-high" };
  if (imp === "H") return { text: "HIGH PRIORITY", className: "gw-priority-high" };
  if (imp === "M") return { text: "MEDIUM PRIORITY", className: "gw-priority-med" };
  return { text: "LOW PRIORITY", className: "gw-priority-low" };
}

function severityForRank(i: number): { label: string; className: string } {
  if (i === 0) return { label: "CRITICAL", className: "gw-sev-critical" };
  if (i <= 2) return { label: "HIGH", className: "gw-sev-high" };
  return { label: "MEDIUM", className: "gw-sev-medium" };
}

function reportToMarkdown(r: WeeklyReport): string {
  const lines: string[] = [`# Weekly pulse — ${r.week ?? ""}`, ""];
  const themes = r.topThemes ?? [];
  if (themes.length) {
    lines.push("## Themes", "");
    for (const t of themes) {
      const vol = themeVolume(t) ? ` (${themeVolume(t)})` : "";
      lines.push(`- **${t.name ?? "Theme"}**${vol}`);
    }
    lines.push("");
  }
  if (r.noteText) {
    lines.push("## Note", "", r.noteText, "");
  }
  if (Array.isArray(r.quotes) && r.quotes.length) {
    lines.push("## Quotes", "");
    lines.push(JSON.stringify(r.quotes, null, 2), "");
  }
  if (Array.isArray(r.actionIdeas) && r.actionIdeas.length) {
    lines.push("## Action ideas", "");
    lines.push(JSON.stringify(r.actionIdeas, null, 2), "");
  }
  if (r.wordCount != null) {
    lines.push(`_Word count: ${r.wordCount}_`, "");
  }
  return lines.join("\n");
}

function downloadText(filename: string, body: string) {
  const blob = new Blob([body], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function Home() {
  const initialWeek = useMemo(() => {
    const iso = dateToIsoWeek(new Date());
    return formatIsoWeek(iso.y, iso.w);
  }, []);
  const [windowEndWeek] = useState(initialWeek);
  const [weekBucket, setWeekBucket] = useState(initialWeek);
  const [recipientEmail, setRecipientEmail] = useState("");
  const [recipientName, setRecipientName] = useState("");
  const [sendNow, setSendNow] = useState(false);

  const [runId, setRunId] = useState<string | null>(null);
  const [runWeek, setRunWeek] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("idle");
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastWarning, setLastWarning] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [lastGenerated, setLastGenerated] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    const t = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/runs/${runId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as RunStatus;
        setStatus(data.status);
        setLastError(data.error || null);
        const phase6Warning =
          data.phaseStatus &&
          typeof data.phaseStatus === "object" &&
          data.phaseStatus["phase6_warning"] &&
          typeof data.phaseStatus["phase6_warning"] === "object"
            ? (data.phaseStatus["phase6_warning"] as Record<string, unknown>)
            : null;
        const warningDetail =
          phase6Warning && typeof phase6Warning.detail === "string"
            ? phase6Warning.detail
            : null;
        setLastWarning(
          warningDetail
            ? `Immediate send failed on provider network; local draft fallback created. (${warningDetail})`
            : null,
        );
        if (data.status === "succeeded" || data.status === "failed") {
          clearInterval(t);
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setLastError(msg);
        clearInterval(t);
      }
    }, 1500);
    return () => clearInterval(t);
  }, [runId]);

  useEffect(() => {
    if (status !== "succeeded" || !runWeek) {
      setReport(null);
      setReportError(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setReportError(null);
      for (let i = 0; i < 6; i++) {
        try {
          const res = await fetch(
            `${API_BASE}/reports/weekly?week=${encodeURIComponent(runWeek)}`,
          );
          if (res.ok) {
            const data = (await res.json()) as WeeklyReport;
            if (!cancelled) {
              setReport(data);
              setLastGenerated(new Date().toLocaleString());
            }
            return;
          }
        } catch {
          /* retry */
        }
        await new Promise((r) => setTimeout(r, 400));
      }
      if (!cancelled) setReportError("Report not ready yet. Try again from the API or re-run.");
    })();
    return () => {
      cancelled = true;
    };
  }, [status, runWeek]);

  async function startRun() {
    setRunId(null);
    setRunWeek(weekBucket);
    setStatus("starting");
    setLastError(null);
    setLastWarning(null);
    setReport(null);
    setReportError(null);
    setBusy(true);

    const body: Record<string, unknown> = {
      weekBucket,
      triggerType: "ui",
      recipientEmail: recipientEmail || null,
      recipientName: recipientName || null,
      sendNow,
      chunked: true,
      maxReviews: 200,
      maxChars: 30000,
    };

    try {
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
      const data = (await res.json()) as { runId: string };
      setRunId(data.runId);
      setStatus("running");
    } catch (e: unknown) {
      setStatus("failed");
      setLastError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const hasPulse = Boolean(report && status === "succeeded");
  const weekStrip = useMemo(() => eightWeeksEndingAt(windowEndWeek), [windowEndWeek]);

  const sortedThemes = useMemo(() => {
    const t = report?.topThemes ?? [];
    return [...t].sort((a, b) => themeVolume(b) - themeVolume(a)).slice(0, 5);
  }, [report]);

  const totalReviewMentions = useMemo(() => {
    return sortedThemes.reduce((s, x) => s + themeVolume(x), 0);
  }, [sortedThemes]);

  const quotes = useMemo(() => {
    const raw = report?.quotes ?? [];
    return raw.map(quoteText).filter(Boolean).slice(0, 5);
  }, [report]);

  const actions = useMemo(() => {
    const raw = report?.actionIdeas ?? [];
    return raw.map(asAction).filter((a) => (a.idea || "").trim());
  }, [report]);

  return (
    <>
      <Head>
        <title>Groww Weekly Pulse</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta
          name="description"
          content="Your weekly digest of user feedback insights — themes, quotes, and strategic actions."
        />
      </Head>

      <div className="ra-shell">
        <aside className="ra-sidebar">
          <div className="ra-sidebar-brand">dashboard</div>
          <p className="ra-sidebar-caption">
            Pipeline status and run identifier (aligned with Groww Weekly Pulse agent layout).
          </p>
          <hr className="ra-sidebar-hr" />

          <div
            className={`ra-phase-step ${weekBucket.trim() ? "ra-phase-done" : "ra-phase-pending"}`}
          >
            <span className="ra-num">1</span>
            <span>Week &amp; email</span>
          </div>
          <div className={`ra-phase-step ${runId ? "ra-phase-done" : "ra-phase-pending"}`}>
            <span className="ra-num">2</span>
            <span>Generate pulse</span>
          </div>
          <div
            className={`ra-phase-step ${status === "succeeded" ? "ra-phase-done" : "ra-phase-pending"}`}
          >
            <span className="ra-num">3</span>
            <span>Review insights</span>
          </div>

          <div className="ra-sidebar-status">
            <strong>Run</strong>
            {runId ? (
              <code style={{ fontSize: "0.7rem", wordBreak: "break-all", display: "block" }}>
                {runId}
              </code>
            ) : (
              "—"
            )}
            <div style={{ marginTop: "0.5rem" }}>
              <span className={statusPillClass(status)}>{status}</span>
            </div>
          </div>
        </aside>

        <main className="ra-main">
          <div className="ra-hero" style={{ textAlign: "left", padding: "1.5rem" }}>
            <h1 className="gw-dash-title">Groww Weekly Pulse</h1>
            <p className="gw-dash-sub">Your weekly digest of user feedback insights</p>

            <div className="gw-last-gen">
              <span className="gw-dot" aria-hidden />
              <span>
                Last generated:{" "}
                {lastGenerated ?? (hasPulse ? "—" : "Not yet — run Generate Pulse")}
              </span>
            </div>

            <button
              type="button"
              className="ra-btn ra-btn-primary gw-btn-pulse"
              onClick={startRun}
              disabled={busy}
            >
              {busy ? "Generating…" : "Generate Pulse"}
            </button>

            <div style={{ marginTop: "1rem", fontSize: "0.8125rem", color: "#94a3b8" }}>
              API: <code style={{ fontSize: "0.75rem" }}>{API_BASE}</code>
            </div>
          </div>

          <section className="ra-share-card">
            <h2 className="gw-label-upper" style={{ marginBottom: "0.5rem" }}>
              Pipeline settings
            </h2>
            <p className="ra-muted" style={{ marginTop: 0 }}>
              ISO week for this run, optional recipient for draft/email (Review Pulse API).
            </p>
            <div className="gw-settings-grid">
              <div className="ra-field" style={{ marginBottom: 0 }}>
                <label className="ra-label" htmlFor="weekBucket">
                  Week bucket
                </label>
                <input
                  id="weekBucket"
                  className="ra-input"
                  value={weekBucket}
                  onChange={(e) => setWeekBucket(e.target.value)}
                  placeholder="2026-W12"
                  autoComplete="off"
                />
              </div>
              <div className="ra-field" style={{ marginBottom: 0 }}>
                <label className="ra-label" htmlFor="recipientEmail">
                  Recipient email
                </label>
                <input
                  id="recipientEmail"
                  className="ra-input"
                  type="email"
                  value={recipientEmail}
                  onChange={(e) => setRecipientEmail(e.target.value)}
                  placeholder="team-lead@company.com"
                  autoComplete="email"
                />
              </div>
              <div className="ra-field" style={{ marginBottom: 0 }}>
                <label className="ra-label" htmlFor="recipientName">
                  Recipient name
                </label>
                <input
                  id="recipientName"
                  className="ra-input"
                  value={recipientName}
                  onChange={(e) => setRecipientName(e.target.value)}
                  placeholder="Optional"
                  autoComplete="name"
                />
              </div>
              <label className="ra-row-check" style={{ marginBottom: 0, alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={sendNow}
                  onChange={(e) => setSendNow(e.target.checked)}
                />
                <span>Send immediately (Gmail MVP)</span>
              </label>
            </div>
            {lastError ? <div className="ra-email-error">{lastError}</div> : null}
            {lastWarning ? <div className="ra-email-error">{lastWarning}</div> : null}
            {reportError ? <div className="ra-email-error">{reportError}</div> : null}
          </section>

          <section className="ra-share-card" style={{ marginTop: "1rem" }}>
            <p className="gw-label-upper">Review analytics</p>
            <div className="gw-week-strip" role="group" aria-label="Week window">
              {weekStrip.map((w, i) => (
                <button
                  key={w}
                  type="button"
                  className={`gw-week-pill ${w === weekBucket ? "gw-week-pill-active" : ""}`}
                  onClick={() => setWeekBucket(w)}
                  title={w}
                >
                  W{i + 1}
                </button>
              ))}
            </div>
            <p className="gw-chart-caption">
              Review volume over time — Current: 8 week window ending{" "}
              <strong style={{ color: "#cbd5e1" }}>{windowEndWeek}</strong> (W8 = latest week in window).
            </p>
          </section>

          {hasPulse && report ? (
            <>
              <section className="ra-share-card" style={{ marginTop: "1rem" }}>
                <p className="gw-label-upper">Top 5 emerging themes</p>
                <div className="gw-theme-list">
                  {sortedThemes.map((t, idx) => (
                    <div key={`${t.name ?? "t"}-${idx}`} className="gw-theme-line">
                      <span className="gw-bolt" aria-hidden>
                        ⚡
                      </span>
                      <span>
                        {t.name ?? "Theme"}{" "}
                        <span className="gw-count">({themeVolume(t)})</span>
                      </span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="ra-share-card" style={{ marginTop: "1rem" }}>
                <p className="gw-label-upper">Current week insights (8 weeks)</p>
                <div className="gw-metric-grid">
                  <div className="gw-metric-card">
                    <div className="gw-metric-label">TOTAL REVIEWS</div>
                    <div className="gw-metric-value">{totalReviewMentions || "—"}</div>
                    <div className="gw-metric-delta muted">Mentions in top themes (window)</div>
                  </div>
                  <div className="gw-metric-card">
                    <div className="gw-metric-label">TIME PERIOD</div>
                    <div className="gw-metric-value" style={{ fontSize: "1rem" }}>
                      {runWeek || weekBucket}
                    </div>
                    <div className="gw-metric-delta muted">ISO week · 8-week strip</div>
                  </div>
                  <div className="gw-metric-card">
                    <div className="gw-metric-label">NOTE WORDS</div>
                    <div className="gw-metric-value">{report.wordCount ?? "—"}</div>
                    <div className="gw-metric-delta muted">Target ≤250</div>
                  </div>
                </div>
              </section>

              <section className="ra-share-card" style={{ marginTop: "1rem" }}>
                <div className="gw-subsection-title">
                  <span aria-hidden>⚠️</span> Themes requiring immediate action
                </div>
                <div className="gw-alert-grid">
                  {sortedThemes.slice(0, 3).map((t, i) => {
                    const sev = severityForRank(i);
                    return (
                      <div key={`${t.name ?? "a"}-${i}`} className="gw-alert-card">
                        <div className="gw-alert-top">
                          <span className="gw-alert-theme">{t.name}</span>
                          <span className={`gw-sev ${sev.className}`}>{sev.label}</span>
                        </div>
                        <p className="gw-alert-sub">
                          Prioritize feedback volume and user impact for “{t.name}” this sprint.
                        </p>
                      </div>
                    );
                  })}
                </div>
              </section>

              <section className="ra-share-card" style={{ marginTop: "1rem" }}>
                <p className="gw-label-upper">Raw user voice</p>
                <div className="gw-quote-list">
                  {quotes.map((q, i) => (
                    <blockquote key={i} className="gw-quote-card">
                      &ldquo;{q}&rdquo;
                    </blockquote>
                  ))}
                </div>
              </section>

              <section className="ra-share-card" style={{ marginTop: "1rem" }}>
                <p className="gw-label-upper">Strategic action ideas</p>
                {actions.map((a, i) => {
                  const pr = priorityLabel(a);
                  return (
                    <div key={i} className="gw-action-card">
                      <span className={`gw-priority ${pr.className}`}>{pr.text}</span>
                      <p className="gw-action-text">{a.idea}</p>
                    </div>
                  );
                })}
              </section>

              {report.noteText ? (
                <section className="ra-share-card" style={{ marginTop: "1rem" }}>
                  <p className="gw-label-upper">Pulse note</p>
                  <div className="ra-note-preview" style={{ maxHeight: "none" }}>
                    {report.noteText}
                  </div>
                </section>
              ) : null}

              <div className="ra-actions" style={{ marginTop: "1rem" }}>
                <button
                  type="button"
                  className="ra-btn ra-btn-secondary"
                  onClick={() =>
                    downloadText(
                      `weekly-pulse-${report.week ?? runWeek ?? "report"}.md`,
                      reportToMarkdown(report),
                    )
                  }
                >
                  Download Markdown
                </button>
              </div>
            </>
          ) : (
            <section className="ra-share-card" style={{ marginTop: "1rem" }}>
              <p className="ra-muted" style={{ margin: 0 }}>
                Run <strong>Generate Pulse</strong> to populate themes, quotes, and actions (same flow
                as{" "}
                <a
                  href="https://groww-weekly-pulse-agent.vercel.app/"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  groww-weekly-pulse-agent.vercel.app
                </a>
                ).
              </p>
            </section>
          )}

          <details className="ra-details" style={{ marginTop: "1.5rem" }}>
            <summary>API &amp; data</summary>
            <p>
              Set <code>NEXT_PUBLIC_API_BASE_URL</code> to your Review Pulse backend. Sentiment and
              week-over-week deltas are not in the API payload yet; metrics use theme mention counts
              and ISO week labels.
            </p>
          </details>
        </main>
      </div>
    </>
  );
}
