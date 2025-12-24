import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/flow-runs/task-run/$id")({
	beforeLoad: ({ params, search }) => {
		redirect({
			to: "/runs/task-run/$id",
			params: { id: params.id },
			search,
			throw: true,
		});
	},
});
