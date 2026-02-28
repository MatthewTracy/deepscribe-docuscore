"use client";

import { useResults } from "@/lib/data";
import { LoadingPage, ErrorState } from "@/components/LoadingState";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function NotesIndexPage() {
  const { data, loading, error } = useResults();
  const router = useRouter();

  useEffect(() => {
    if (data && data.reports.length > 0) {
      // Redirect to worst-scoring note (notes are ranked worst-to-best)
      const worst = [...data.reports].sort(
        (a, b) => a.overall_score - b.overall_score
      )[0];
      router.replace(`/notes/${encodeURIComponent(worst.note_id)}`);
    }
  }, [data, router]);

  if (loading) return <LoadingPage />;
  if (error || !data) return <ErrorState message={error || "No data available"} />;

  if (data.reports.length === 0) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-sm text-muted">No notes found in the evaluation data.</p>
      </div>
    );
  }

  return <LoadingPage />;
}
