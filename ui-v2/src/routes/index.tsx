import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
	component: function RouteComponent() {
		return null;
	},
	beforeLoad: ({ location }) => {
		if (location.pathname === "/") {
			redirect({ to: "/dashboard", throw: true });
		}
	},
});
