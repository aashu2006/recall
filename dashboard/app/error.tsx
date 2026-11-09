"use client";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-6">
      <h1 className="font-semibold">Couldn&apos;t load data</h1>
      <p className="mt-1 text-sm text-muted">{error.message || "Something went wrong talking to the database."}</p>
      <button onClick={reset} className="mt-4 rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-bg">
        Try again
      </button>
    </div>
  );
}
