import { createFileRoute } from "@tanstack/react-router";
import { addDays, startOfDay } from "date-fns";
import { $api } from "../api/service";

export const Route = createFileRoute("/events_/event/$date/$eventId")({
	component: RouteComponent,
	loader: async ({ context, params }) => {
		return await context.queryClient.ensureQueryData(
			$api.queryOptions("post", "/events/filter", {
				body: {
					limit: 1,
					filter: {
						order: "DESC",
						id: {
							id: [params.eventId],
						},
						occurred: {
							since: startOfDay(params.date).toISOString(),
							until: addDays(startOfDay(params.date), 1).toISOString(),
						},
					},
				},
			}),
		);
	},
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
