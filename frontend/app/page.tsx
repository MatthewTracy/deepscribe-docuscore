"use client";

import { useResults } from "@/lib/data";
import { LoadingPage, ErrorState } from "@/components/LoadingState";
import StatCard from "@/components/StatCard";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  formatNumber,
  formatPercent,
  gateColor,
  scoreBarColor,
  scoreBarWidth,
} from "@/lib/utils";
import type { BatchReport } from "@/lib/types";

// ── Sub-components ──────────────────────────────────────────────────────────

function GateDistribution({ data }: { data: BatchReport }) {
  const gates = ["PASS", "REVIEW", "FAIL"] as const;
  const total = data.total_notes || 1;

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h3 className="mb-4 text-sm font-medium uppercase tracking-wider text-muted">
        Quality Gate Distribution
      </h3>
      <div className="flex gap-3">
        {gates.map((gate) => {
          const count = data.gate_distribution[gate] ?? 0;
          const pct = ((count / total) * 100).toFixed(0);
          return (
            <div
              key={gate}
              className={`flex flex-1 flex-col items-center rounded-lg border px-3 py-4 ${gateColor(gate)}`}
            >
              <span className="text-2xl font-bold">{count}</span>
              <span className="text-xs font-medium">{gate}</span>
              <span className="mt-1 text-xs opacity-70">{pct}%</span>
            </div>
          );
        })}
      </div>
      {/* Stacked bar */}
      <div className="mt-4 flex h-3 overflow-hidden rounded-full bg-background">
        {gates.map((gate) => {
          const count = data.gate_distribution[gate] ?? 0;
          const pct = (count / total) * 100;
          const colors = {
            PASS: "bg-gate-pass",
            REVIEW: "bg-gate-review",
            FAIL: "bg-gate-fail",
          };
          return (
            <div
              key={gate}
              className={`${colors[gate]} transition-all`}
              style={{ width: `${pct}%` }}
            />
          );
        })}
      </div>
    </div>
  );
}

function ScoreDistribution({ data }: { data: BatchReport }) {
  // Bucket scores into ranges (overall_score is 0-1)
  const buckets = [
    { label: "0-.2", min: 0, max: 0.2 },
    { label: ".2-.4", min: 0.2, max: 0.4 },
    { label: ".4-.6", min: 0.4, max: 0.6 },
    { label: ".6-.8", min: 0.6, max: 0.8 },
    { label: ".8-1", min: 0.8, max: 1.01 },
  ];

  const counts = buckets.map((b) => ({
    ...b,
    count: data.reports.filter(
      (r) => r.overall_score >= b.min && r.overall_score < b.max
    ).length,
  }));

  const maxCount = Math.max(...counts.map((c) => c.count), 1);

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h3 className="mb-4 text-sm font-medium uppercase tracking-wider text-muted">
        Score Distribution
      </h3>
      <div className="flex items-end gap-2" style={{ height: "140px" }}>
        {counts.map((bucket) => {
          const heightPct = (bucket.count / maxCount) * 100;
          const color =
            bucket.min >= 0.8
              ? "bg-gate-pass"
              : bucket.min >= 0.6
                ? "bg-gate-review"
                : bucket.min >= 0.4
                  ? "bg-accent"
                  : "bg-gate-fail";
          return (
            <div key={bucket.label} className="flex flex-1 flex-col items-center gap-1">
              <span className="text-xs font-medium text-muted">
                {bucket.count}
              </span>
              <div className="relative w-full flex items-end" style={{ height: "100px" }}>
                <div
                  className={`w-full rounded-t-md ${color} transition-all`}
                  style={{ height: `${Math.max(heightPct, 2)}%` }}
                />
              </div>
              <span className="text-xs text-muted">{bucket.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function HallucinationBreakdown({ data }: { data: BatchReport }) {
  const types = data.most_common_hallucination_types;
  const entries = Object.entries(types).sort((a, b) => b[1] - a[1]);
  const maxVal = Math.max(...entries.map((e) => e[1]), 1);

  const typeColors: Record<string, string> = {
    fabrication: "bg-gate-fail",
    negation: "bg-severity-major",
    contextual: "bg-gate-review",
    temporal: "bg-accent",
  };

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h3 className="mb-4 text-sm font-medium uppercase tracking-wider text-muted">
        Hallucination Types
      </h3>
      {entries.length === 0 ? (
        <p className="text-sm text-muted">No hallucinations detected</p>
      ) : (
        <div className="space-y-3">
          {entries.map(([type, count]) => (
            <div key={type}>
              <div className="mb-1 flex items-center justify-between">
                <span className="text-sm font-medium capitalize text-foreground">
                  {type}
                </span>
                <span className="text-sm font-mono text-muted">{count}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-background">
                <div
                  className={`h-full rounded-full ${typeColors[type] || "bg-accent"} transition-all`}
                  style={{ width: `${(count / maxVal) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MetaEvalCard({ data }: { data: BatchReport }) {
  if (!data.meta_eval) return null;

  const meta = data.meta_eval;

  return (
    <div className="rounded-xl border border-accent/30 bg-accent/5 p-5">
      <h3 className="mb-4 text-sm font-medium uppercase tracking-wider text-accent">
        Meta-Evaluation (Judge Quality)
      </h3>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <span className="text-xs text-muted">Test Cases</span>
          <p className="text-xl font-bold text-foreground">
            {meta.injected_errors_total}
          </p>
        </div>
        <div>
          <span className="text-xs text-muted">Error Detection Rate</span>
          <p className="text-xl font-bold text-foreground">
            {formatPercent(meta.injected_error_detection_rate)}
          </p>
        </div>
        <div>
          <span className="text-xs text-muted">Errors Caught</span>
          <p className="text-xl font-bold text-foreground">
            {meta.injected_errors_caught} / {meta.injected_errors_total}
          </p>
        </div>
      </div>
      {meta.details.length > 0 && (
        <div className="mt-4 space-y-1">
          {meta.details.map((d, i) => (
            <p key={i} className="text-xs text-muted">
              {d}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function TopNotesTable({ data }: { data: BatchReport }) {
  const router = useRouter();
  const sorted = [...data.reports].sort(
    (a, b) => a.overall_score - b.overall_score
  );
  const bottom5 = sorted.slice(0, 5);

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <h3 className="mb-4 text-sm font-medium uppercase tracking-wider text-muted">
        Lowest-Scoring Notes
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted">
              <th className="pb-2 pr-4">Note ID</th>
              <th className="pb-2 pr-4">Score</th>
              <th className="pb-2 pr-4">Gate</th>
              <th className="pb-2 pr-4">Hallucinations</th>
              <th className="pb-2">Omissions</th>
            </tr>
          </thead>
          <tbody>
            {bottom5.map((report) => (
              <tr
                key={report.note_id}
                role="link"
                tabIndex={0}
                onClick={() => router.push(`/notes/${encodeURIComponent(report.note_id)}`)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); router.push(`/notes/${encodeURIComponent(report.note_id)}`); } }}
                className="border-b border-border/50 last:border-0 cursor-pointer hover:bg-surface-hover transition-colors"
              >
                <td className="py-2 pr-4">
                  <Link
                    href={`/notes/${encodeURIComponent(report.note_id)}`}
                    className="font-mono text-accent hover:underline"
                  >
                    {report.note_id}
                  </Link>
                </td>
                <td className="py-2 pr-4">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-16 overflow-hidden rounded-full bg-background">
                      <div
                        className={`h-full rounded-full ${scoreBarColor(report.overall_score)}`}
                        style={{ width: scoreBarWidth(report.overall_score) }}
                      />
                    </div>
                    <span className="font-mono text-xs">
                      {formatNumber(report.overall_score)}
                    </span>
                  </div>
                </td>
                <td className="py-2 pr-4">
                  <span
                    className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${gateColor(report.quality_gate.decision)}`}
                  >
                    {report.quality_gate.decision}
                  </span>
                </td>
                <td className="py-2 pr-4 font-mono text-xs">
                  {report.llm_judge.hallucinations.length}
                </td>
                <td className="py-2 font-mono text-xs">
                  {report.llm_judge.omissions.length}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { data, loading, error } = useResults();

  if (loading) return <LoadingPage />;
  if (error || !data) return <ErrorState message={error || "No data available"} />;

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Evaluation Dashboard
        </h1>
        <p className="mt-1 text-sm text-muted">
          {data.total_notes} clinical notes evaluated &middot;{" "}
          <span className={data.avg_overall_score >= 0.8 ? "text-gate-pass" : data.avg_overall_score >= 0.6 ? "text-gate-review" : "text-gate-fail"}>
            {formatPercent(data.avg_overall_score)} avg quality
          </span>
          {" "}&middot;{" "}
          {data.gate_distribution["PASS"] ?? 0} passed,{" "}
          {data.gate_distribution["REVIEW"] ?? 0} review,{" "}
          {data.gate_distribution["FAIL"] ?? 0} failed
        </p>
      </div>

      {/* Hero stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard
          label="Total Notes"
          value={data.total_notes}
          icon={
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          }
        />
        <StatCard
          label="Avg Score"
          value={formatPercent(data.avg_overall_score)}
          sublabel="weighted quality score"
          accent={
            data.avg_overall_score >= 0.8
              ? "text-gate-pass"
              : data.avg_overall_score >= 0.6
                ? "text-gate-review"
                : "text-gate-fail"
          }
          icon={
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
            </svg>
          }
        />
        <StatCard
          label="Hallucinations"
          value={data.total_hallucinations}
          accent={data.total_hallucinations > 0 ? "text-gate-fail" : "text-gate-pass"}
          icon={
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          }
        />
        <StatCard
          label="Omissions"
          value={data.total_omissions}
          accent={data.total_omissions > 0 ? "text-severity-major" : "text-gate-pass"}
          icon={
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
      </div>

      {/* Charts row */}
      <div className="grid gap-4 lg:grid-cols-2">
        <GateDistribution data={data} />
        <ScoreDistribution data={data} />
      </div>

      {/* Hallucination breakdown + meta-eval */}
      <div className="grid gap-4 lg:grid-cols-2">
        <HallucinationBreakdown data={data} />
        <MetaEvalCard data={data} />
      </div>

      {/* Lowest scoring notes table */}
      <TopNotesTable data={data} />
    </div>
  );
}
