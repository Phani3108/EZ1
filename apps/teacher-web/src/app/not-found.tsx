import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col">
      <div className="h-2 bg-green-600" />

      <div className="flex-1 flex flex-col items-center justify-center px-4 text-center">
        <p className="text-8xl font-black text-muted-foreground/20 select-none">404</p>
        <h1 className="mt-4 text-2xl font-bold">Page Not Found</h1>
        <p className="mt-2 text-muted-foreground max-w-sm">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
        <Link
          href="/today"
          className="mt-6 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
        >
          Back to Today&apos;s Classes
        </Link>
      </div>

      <div className="h-2 bg-red-600" />
    </div>
  );
}
