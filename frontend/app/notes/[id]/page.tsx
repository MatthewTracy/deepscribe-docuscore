"use client";

import { useParams } from "next/navigation";
import { useResults, useNotes } from "@/lib/data";
import { LoadingPage, ErrorState } from "@/components/LoadingState";
import NoteExplorer from "./NoteExplorer";

export default function NoteDetailPage() {
  const params = useParams();
  const noteId = typeof params.id === "string" ? decodeURIComponent(params.id) : "";
  const results = useResults();
  const notes = useNotes();

  const loading = results.loading || notes.loading;
  const error = results.error || notes.error;

  if (loading) return <LoadingPage />;
  if (error || !results.data)
    return <ErrorState message={error || "No data available"} />;

  return (
    <NoteExplorer
      batchReport={results.data}
      notesData={notes.data || []}
      activeNoteId={noteId}
    />
  );
}
