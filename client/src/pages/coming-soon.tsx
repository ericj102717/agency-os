import { Construction } from "lucide-react";
import { Card, CardContent } from "@/components/ui-widgets";

export function ComingSoon({ title }: { title: string }) {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <Card className="max-w-md">
        <CardContent className="p-8 text-center">
          <Construction className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-foreground mb-2">{title}</h2>
          <p className="text-sm text-muted-foreground">
            This page is coming in Phase 2 of the React migration. The backend data is ready —
            the React component just needs to be built.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
