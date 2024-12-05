import { createFileRoute } from "@tanstack/react-router";

import { ConcurrencyPage } from "@/components/concurrency/concurrency-page";

export const Route = createFileRoute("/concurrency-limits")({
	component: RouteComponent,
});

function RouteComponent() {
	return <ConcurrencyPage />;
}
