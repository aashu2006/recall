import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-20 text-center">
      <p className="label">Not in the register</p>
      <h1 className="mt-2 font-serif text-[28px] font-semibold">This page doesn&apos;t exist</h1>
      <Link href="/" className="mt-4 inline-block rounded text-[15px] text-ink underline decoration-ink/30 underline-offset-4 hover:decoration-ink">
        Back to the order book
      </Link>
    </div>
  );
}
