import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-20 text-center">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <Link href="/" className="mt-2 inline-block text-primary hover:underline">
        Back to orders
      </Link>
    </div>
  );
}
