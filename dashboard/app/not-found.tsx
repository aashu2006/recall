import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-16 text-center">
      <h1 className="text-lg font-semibold">Not found</h1>
      <Link href="/" className="mt-2 inline-block text-sm text-ink underline underline-offset-4">
        Back to orders
      </Link>
    </div>
  );
}
