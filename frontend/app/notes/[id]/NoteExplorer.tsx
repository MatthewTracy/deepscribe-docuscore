"use client";

import { useState } from "react";
import Link from "next/link";
import type {
  BatchReport,
  NoteData,
  EvalReport,
  Hallucination,
  Omission,
  SectionScore,
} from "@/lib/types";
import {
  formatNumber,
  formatPercent,
  gateColor,
  severityColor,
  scoreBarColor,
  scoreBarWidth,
  sectionScoreBarColor,
  classNames,
  sanitizeText,
} from "@/lib/utils";

// ── Sidebar ─────────────────────────────────────────────────────────────────

function NoteSidebar({
  reports,
  activeNoteId,
}: {
  reports: EvalReport[];
  activeNoteId: string;
}) {
  const sorted = [...reports].sort((a, b) => a.overall_score - b.overall_score);

  return (
    <div className="flex flex-col gap-1 overflow-y-auto pr-2" style={{ maxHeight: "calc(100vh - 200px)" }}>
      {sorted.map((report) => {
        const isActive = report.note_id === activeNoteId;
        return (
          <Link
            key={report.note_id}
            href={`/notes/${encodeURIComponent(report.note_id)}`}
            className={classNames(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
              isActive
                ? "bg-accent/15 text-accent border border-accent/30"
                : "text-muted hover:text-foreground hover:bg-surface-hover border border-transparent"
            )}
          >
            <span className="flex-1 truncate font-mono text-xs">
              {report.note_id}
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono">
                {formatNumber(report.overall_score)}
              </span>
              <span
                className={`inline-flex h-2 w-2 rounded-full ${
                  report.quality_gate.decision === "PASS"
                    ? "bg-gate-pass"
                    : report.quality_gate.decision === "REVIEW"
                      ? "bg-gate-review"
                      : "bg-gate-fail"
                }`}
              />
            </div>
          </Link>
        );
      })}
    </div>
  );
}

// ── Quick stats bar ──────────────────────────────────────────────────────────

function QuickStats({ report }: { report: EvalReport }) {
  const halCount = report.llm_judge.hallucinations.length;
  const omCount = report.llm_judge.omissions.length;
  const det = report.deterministic;

  const stats = [
    {
      label: "Overall",
      value: formatPercent(report.overall_score),
      color: report.overall_score >= 0.8 ? "text-gate-pass" : report.overall_score >= 0.6 ? "text-gate-review" : "text-gate-fail",
    },
    {
      label: "Completeness",
      value: formatPercent(det.section_completeness_score),
      color: det.section_completeness_score >= 0.75 ? "text-gate-pass" : "text-gate-review",
    },
    {
      label: "Grounding",
      value: `${(det.entity_grounding_rate * 100).toFixed(0)}%`,
      color: det.entity_grounding_rate >= 0.7 ? "text-gate-pass" : "text-gate-review",
    },
    {
      label: "Hallucinations",
      value: String(halCount),
      color: halCount === 0 ? "text-gate-pass" : "text-gate-fail",
    },
    {
      label: "Omissions",
      value: String(omCount),
      color: omCount === 0 ? "text-gate-pass" : "text-severity-major",
    },
  ];

  return (
    <div className="grid grid-cols-3 gap-3 sm:grid-cols-5">
      {stats.map((s) => (
        <div
          key={s.label}
          className="rounded-lg border border-border bg-surface px-3 py-2.5 text-center"
        >
          <div className={classNames("text-lg font-bold tabular-nums", s.color)}>
            {s.value}
          </div>
          <div className="text-[10px] font-medium uppercase tracking-wider text-muted">
            {s.label}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Transcript / SOAP split view ────────────────────────────────────────────

function SplitView({
  transcript,
  soapNote,
}: {
  transcript: string;
  soapNote: string;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="rounded-xl border border-border bg-surface p-4">
        <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-muted">
          Transcript
        </h3>
        <div className="max-h-[28rem] overflow-y-auto">
          <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground/90">
            {sanitizeText(transcript)}
          </pre>
        </div>
      </div>
      <div className="rounded-xl border border-border bg-surface p-4">
        <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-muted">
          SOAP Note
        </h3>
        <div className="max-h-[28rem] overflow-y-auto">
          <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground/90">
            {sanitizeText(soapNote)}
          </pre>
        </div>
      </div>
    </div>
  );
}

// ── Placeholder for missing notes data ──────────────────────────────────────

function NoTranscriptView() {
  return (
    <div className="rounded-xl border border-border bg-surface p-6 text-center">
      <p className="text-sm text-muted">
        Transcript and SOAP note data not available. Place{" "}
        <code className="rounded bg-background px-1.5 py-0.5 font-mono text-xs">notes.json</code>{" "}
        in <code className="rounded bg-background px-1.5 py-0.5 font-mono text-xs">public/data/</code>{" "}
        to enable the split view.
      </p>
    </div>
  );
}

// ── Tabs ────────────────────────────────────────────────────────────────────

type TabKey = "actions" | "hallucinations" | "omissions" | "sections" | "details";

const tabs: { key: TabKey; label: string }[] = [
  { key: "actions", label: "Action Items" },
  { key: "hallucinations", label: "Hallucinations" },
  { key: "omissions", label: "Omissions" },
  { key: "sections", label: "Section Scores" },
  { key: "details", label: "Details" },
];

// ── Action Items tab ────────────────────────────────────────────────────────

const SEVERITY_ORDER: Record<string, number> = { critical: 0, major: 1, minor: 2 };

interface ActionItem {
  action: "Remove" | "Revise" | "Add";
  severity: "critical" | "major" | "minor";
  target: string;
  reason: string;
  section?: string;
}

function ActionItemsTab({
  report,
}: {
  report: EvalReport;
}) {
  const items: ActionItem[] = [];

  // Hallucinations → Remove / Revise actions
  for (const h of report.llm_judge.hallucinations) {
    const action = h.hallucination_type === "fabrication" ? "Remove" : "Revise";
    items.push({
      action,
      severity: h.severity,
      target: h.note_text,
      reason: h.explanation,
    });
  }

  // Omissions → Add actions
  for (const o of report.llm_judge.omissions) {
    items.push({
      action: "Add",
      severity: o.clinical_importance,
      target: o.transcript_text,
      reason: o.explanation,
      section: o.expected_section,
    });
  }

  // Sort by severity
  items.sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);

  if (items.length === 0) {
    return (
      <div className="rounded-lg bg-gate-pass/10 p-6 text-center">
        <p className="text-sm font-medium text-gate-pass">No action items - this note passed all checks</p>
      </div>
    );
  }

  const actionStyles = {
    Remove: { bg: "bg-gate-fail/8", border: "border-gate-fail/20", badge: "bg-gate-fail/15 text-gate-fail" },
    Revise: { bg: "bg-severity-major/8", border: "border-severity-major/20", badge: "bg-severity-major/15 text-severity-major" },
    Add: { bg: "bg-gate-review/8", border: "border-gate-review/20", badge: "bg-gate-review/15 text-gate-review" },
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">
        {items.length} action{items.length !== 1 ? "s" : ""} to improve this note - sorted by clinical priority
      </p>
      {items.map((item, i) => {
        const style = actionStyles[item.action];
        return (
          <div
            key={i}
            className={classNames("rounded-xl border p-4", style.bg, style.border)}
          >
            <div className="mb-2 flex items-center gap-2">
              <span className={classNames("inline-flex rounded-full px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider", style.badge)}>
                {item.action}
              </span>
              <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${severityColor(item.severity)}`}>
                {item.severity}
              </span>
              {item.section && (
                <span className="rounded-full bg-surface px-2 py-0.5 text-xs text-muted">
                  {item.section}
                </span>
              )}
            </div>
            <div className="mb-2 rounded-lg bg-background px-3 py-2">
              <p className="text-sm text-foreground/90">
                &ldquo;{sanitizeText(item.target)}&rdquo;
              </p>
            </div>
            <p className="text-xs leading-relaxed text-muted">{item.reason}</p>
          </div>
        );
      })}
    </div>
  );
}

// ── Hallucinations tab ──────────────────────────────────────────────────────

function HallucinationsTab({
  hallucinations,
}: {
  hallucinations: Hallucination[];
}) {
  if (hallucinations.length === 0) {
    return (
      <div className="rounded-lg bg-gate-pass/10 p-4 text-center">
        <p className="text-sm text-gate-pass">No hallucinations detected</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {hallucinations.map((h, i) => (
        <div
          key={i}
          className="rounded-xl border border-gate-fail/20 bg-gate-fail/5 p-4"
        >
          <div className="mb-2 flex items-center gap-2">
            <span
              className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${severityColor(h.severity)}`}
            >
              {h.severity}
            </span>
            <span className="rounded-full bg-surface px-2 py-0.5 text-xs capitalize text-muted">
              {h.hallucination_type}
            </span>
          </div>
          <div className="mb-3 rounded-lg bg-gate-fail/10 px-3 py-2">
            <p className="text-sm font-medium text-gate-fail">
              &ldquo;{sanitizeText(h.note_text)}&rdquo;
            </p>
          </div>
          <p className="mb-2 text-sm text-foreground/80">{h.explanation}</p>
          {h.transcript_context && (
            <div className="rounded-lg bg-background px-3 py-2">
              <span className="text-xs text-muted">Transcript context:</span>
              <p className="mt-1 text-xs text-foreground/70">
                &ldquo;{sanitizeText(h.transcript_context)}&rdquo;
              </p>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Omissions tab ───────────────────────────────────────────────────────────

function OmissionsTab({ omissions }: { omissions: Omission[] }) {
  if (omissions.length === 0) {
    return (
      <div className="rounded-lg bg-gate-pass/10 p-4 text-center">
        <p className="text-sm text-gate-pass">No omissions detected</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {omissions.map((o, i) => (
        <div
          key={i}
          className="rounded-xl border border-gate-review/20 bg-gate-review/5 p-4"
        >
          <div className="mb-2 flex items-center gap-2">
            <span
              className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${severityColor(o.clinical_importance)}`}
            >
              {o.clinical_importance}
            </span>
            <span className="rounded-full bg-surface px-2 py-0.5 text-xs text-muted">
              Expected in: {o.expected_section}
            </span>
          </div>
          <div className="mb-3 rounded-lg bg-gate-review/10 px-3 py-2">
            <p className="text-sm font-medium text-gate-review">
              &ldquo;{sanitizeText(o.transcript_text)}&rdquo;
            </p>
          </div>
          <p className="text-sm text-foreground/80">{o.explanation}</p>
        </div>
      ))}
    </div>
  );
}

// ── Section Scores tab ──────────────────────────────────────────────────────

function SectionScoresTab({
  sectionScores,
}: {
  sectionScores: Record<string, SectionScore>;
}) {
  const sections = Object.entries(sectionScores);

  if (sections.length === 0) {
    return (
      <div className="rounded-lg bg-surface p-4 text-center">
        <p className="text-sm text-muted">No section scores available</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {sections.map(([name, score]) => (
        <div key={name} className="rounded-xl border border-border bg-surface p-4">
          <h4 className="mb-3 text-sm font-semibold capitalize text-foreground">
            {name}
          </h4>
          <div className="grid gap-3 sm:grid-cols-3">
            {(
              [
                ["Completeness", score.completeness],
                ["Faithfulness", score.faithfulness],
                ["Clinical Accuracy", score.clinical_accuracy],
              ] as const
            ).map(([label, val]) => (
              <div key={label}>
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-xs text-muted">{label}</span>
                  <span className="text-xs font-mono font-medium">
                    {val}/5
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-background">
                  <div
                    className={`h-full rounded-full ${sectionScoreBarColor(val)} transition-all`}
                    style={{ width: scoreBarWidth(val, 5) }}
                  />
                </div>
              </div>
            ))}
          </div>
          {score.reasoning && (
            <p className="mt-3 text-xs leading-relaxed text-muted">
              {score.reasoning}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Details tab ─────────────────────────────────────────────────────────────

function DetailsTab({ report }: { report: EvalReport }) {
  const det = report.deterministic;
  const judge = report.llm_judge;

  return (
    <div className="space-y-4">
      {/* Quality gate */}
      <div className="rounded-xl border border-border bg-surface p-4">
        <h4 className="mb-3 text-sm font-semibold text-foreground">
          Quality Gate
        </h4>
        <div className="flex items-center gap-3">
          <span
            className={`inline-flex rounded-full border px-3 py-1 text-sm font-bold ${gateColor(report.quality_gate.decision)}`}
          >
            {report.quality_gate.decision}
          </span>
          <span className="text-sm text-muted">
            Overall Score: {formatPercent(report.overall_score)}
          </span>
        </div>
        {report.quality_gate.reasons.length > 0 && (
          <ul className="mt-3 space-y-1">
            {report.quality_gate.reasons.map((r, i) => (
              <li key={i} className="text-xs text-muted">
                &bull; {r}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Deterministic metrics */}
      <div className="rounded-xl border border-border bg-surface p-4">
        <h4 className="mb-3 text-sm font-semibold text-foreground">
          Deterministic Metrics
        </h4>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {(["subjective", "objective", "assessment", "plan"] as const).map(
            (s) => (
              <div key={s} className="text-center">
                <div
                  className={`mx-auto mb-1 flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold ${
                    det.sections_present[s]
                      ? "bg-gate-pass/20 text-gate-pass"
                      : "bg-gate-fail/20 text-gate-fail"
                  }`}
                >
                  {det.sections_present[s] ? "Y" : "N"}
                </div>
                <span className="text-xs capitalize text-muted">{s}</span>
              </div>
            )
          )}
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <span className="text-xs text-muted">Section Completeness</span>
            <p className="text-lg font-bold">
              {formatPercent(det.section_completeness_score)}
            </p>
          </div>
          <div>
            <span className="text-xs text-muted">Entity Grounding Rate</span>
            <p className="text-lg font-bold">
              {(det.entity_grounding_rate * 100).toFixed(1)}%
            </p>
          </div>
        </div>
        {det.contradictions.length > 0 && (
          <div className="mt-4">
            <span className="text-xs font-medium text-gate-fail">
              Contradictions ({det.contradictions.length})
            </span>
            <div className="mt-2 space-y-2">
              {det.contradictions.map((c, i) => (
                <div
                  key={i}
                  className="rounded-lg bg-gate-fail/5 p-3 text-xs"
                >
                  <p className="text-foreground/80">
                    <strong>Note:</strong> {c.note_claim}
                  </p>
                  <p className="mt-1 text-muted">
                    <strong>Evidence:</strong> {c.transcript_evidence}
                  </p>
                  <p className="mt-1 text-gate-fail">{c.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* LLM Judge overall reasoning */}
      <div className="rounded-xl border border-border bg-surface p-4">
        <h4 className="mb-3 text-sm font-semibold text-foreground">
          LLM Judge Overall Assessment
        </h4>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs text-muted">Quality:</span>
          <span className="text-sm font-bold">{judge.overall_quality} / 5</span>
        </div>
        <p className="text-sm leading-relaxed text-foreground/80">
          {judge.overall_reasoning}
        </p>
      </div>
    </div>
  );
}

// ── Main NoteExplorer ───────────────────────────────────────────────────────

export default function NoteExplorer({
  batchReport,
  notesData,
  activeNoteId,
}: {
  batchReport: BatchReport;
  notesData: NoteData[];
  activeNoteId: string;
}) {
  const [activeTab, setActiveTab] = useState<TabKey>("actions");

  const report = batchReport.reports.find((r) => r.note_id === activeNoteId);
  const noteData = notesData.find((n) => n.note_id === activeNoteId);

  if (!report) {
    return (
      <ErrorState
        message={`Note "${activeNoteId}" not found in evaluation results.`}
      />
    );
  }

  const hallucinationCount = report.llm_judge.hallucinations.length;
  const omissionCount = report.llm_judge.omissions.length;

  return (
    <div className="flex gap-6">
      {/* Sidebar */}
      <div className="hidden w-64 flex-shrink-0 lg:block">
        <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-muted">
          Notes ({batchReport.reports.length})
        </h3>
        <NoteSidebar
          reports={batchReport.reports}
          activeNoteId={activeNoteId}
        />
      </div>

      {/* Main content */}
      <div className="min-w-0 flex-1 space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">
              <span className="font-mono text-accent">{report.note_id}</span>
            </h1>
            <div className="mt-1 flex items-center gap-3">
              <span
                className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${gateColor(report.quality_gate.decision)}`}
              >
                {report.quality_gate.decision}
              </span>
              <span className="text-sm text-muted">
                Score: {formatPercent(report.overall_score)}
              </span>
            </div>
          </div>
          {/* Mobile note selector */}
          <div className="lg:hidden">
            <select
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"
              value={activeNoteId}
              onChange={(e) => {
                window.location.href = `/notes/${encodeURIComponent(e.target.value)}`;
              }}
            >
              {[...batchReport.reports]
                .sort((a, b) => a.overall_score - b.overall_score)
                .map((r) => (
                  <option key={r.note_id} value={r.note_id}>
                    {r.note_id} ({formatNumber(r.overall_score)})
                  </option>
                ))}
            </select>
          </div>
        </div>

        {/* Quick stats */}
        <QuickStats report={report} />

        {/* Split view */}
        {noteData ? (
          <SplitView
            transcript={noteData.transcript}
            soapNote={noteData.soap_note}
          />
        ) : (
          <NoTranscriptView />
        )}

        {/* Tabs */}
        <div>
          <div className="flex gap-1 border-b border-border pb-px">
            {tabs.map((tab) => {
              let badge: number | null = null;
              if (tab.key === "actions") badge = hallucinationCount + omissionCount;
              if (tab.key === "hallucinations") badge = hallucinationCount;
              if (tab.key === "omissions") badge = omissionCount;

              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={classNames(
                    "relative flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors",
                    activeTab === tab.key
                      ? "text-accent"
                      : "text-muted hover:text-foreground"
                  )}
                >
                  {tab.label}
                  {badge !== null && badge > 0 && (
                    <span
                      className={classNames(
                        "inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-xs font-bold",
                        tab.key === "actions"
                          ? "bg-accent/20 text-accent"
                          : tab.key === "hallucinations"
                            ? "bg-gate-fail/20 text-gate-fail"
                            : "bg-gate-review/20 text-gate-review"
                      )}
                    >
                      {badge}
                    </span>
                  )}
                  {activeTab === tab.key && (
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent" />
                  )}
                </button>
              );
            })}
          </div>

          <div className="pt-4">
            {activeTab === "actions" && (
              <ActionItemsTab report={report} />
            )}
            {activeTab === "hallucinations" && (
              <HallucinationsTab
                hallucinations={report.llm_judge.hallucinations}
              />
            )}
            {activeTab === "omissions" && (
              <OmissionsTab omissions={report.llm_judge.omissions} />
            )}
            {activeTab === "sections" && (
              <SectionScoresTab
                sectionScores={report.llm_judge.section_scores}
              />
            )}
            {activeTab === "details" && <DetailsTab report={report} />}
          </div>
        </div>
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <div className="rounded-xl border border-gate-fail/30 bg-gate-fail/10 px-8 py-6 text-center">
        <p className="text-sm text-gate-fail">{message}</p>
      </div>
    </div>
  );
}
