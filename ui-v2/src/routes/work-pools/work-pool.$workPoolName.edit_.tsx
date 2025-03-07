import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute(
	"/work-pools/work-pool/$workPoolName/edit_",
)({
	component: RouteComponent,
});

function RouteComponent() {
	return <div>Edit Work Pool</div>;
}
