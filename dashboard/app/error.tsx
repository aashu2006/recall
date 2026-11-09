"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <Card className="items-start px-6 py-6">
      <div>
        <h1 className="font-semibold">Couldn&apos;t load this page</h1>
        <p className="mt-1 text-muted-foreground">{error.message || "Something went wrong talking to the database."}</p>
      </div>
      <Button variant="outline" onClick={reset}>
        Try again
      </Button>
    </Card>
  );
}
