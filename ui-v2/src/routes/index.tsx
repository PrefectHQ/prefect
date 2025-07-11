import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
	component: RouteComponent,
	beforeLoad: ({ location }) => {
		if (location.pathname === "/") {
			redirect({ to: "/dashboard", throw: true });
		}
	},
});

function RouteComponent() {
	return null;
}
