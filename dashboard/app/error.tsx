"use client";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="border-y border-rule border-l-2 border-l-red bg-paper-3/60 px-5 py-6 sm:px-6">
      <h1 className="font-serif text-[20px] font-semibold">Couldn&apos;t load the register</h1>
      <p className="mt-1.5 text-[15px] text-soft">{error.message || "Something went wrong talking to the database."}</p>
      <button
        onClick={reset}
        className="mt-5 min-h-10 rounded-md bg-ink px-4 text-sm font-medium text-paper transition-opacity hover:opacity-90"
      >
        Try again
      </button>
    </div>
  );
}
