import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
	component: RouteComponent,
	beforeLoad: ({ location }) => {
		if (location.pathname === "/") {
			throw redirect({ to: "/dashboard" });
		}
	},
});

function RouteComponent() {
	return <></>;
}
