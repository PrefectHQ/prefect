import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/flow-runs/flow-run/$id")({
	beforeLoad: ({ params, search }) => {
		redirect({
			to: "/runs/flow-run/$id",
			params: { id: params.id },
			search,
			throw: true,
		});
	},
});
