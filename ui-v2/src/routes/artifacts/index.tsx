import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/artifacts/")({
	component: RouteComponent,
});

function RouteComponent() {
	return <div>Hello /artifacts!</div>;
}
