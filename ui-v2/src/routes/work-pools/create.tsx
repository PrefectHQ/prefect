import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/work-pools/create")({
	component: RouteComponent,
});

function RouteComponent() {
	return (
		<div>
			<code>/work-pools/create</code>
		</div>
	);
}
