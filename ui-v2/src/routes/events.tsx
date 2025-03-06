import { createFileRoute } from "@tanstack/react-router";
import { $api } from "../api/service";
import { components } from "@/api/prefect";
import { z } from "zod";
import { zodValidator } from "@tanstack/zod-adapter";
import { readEventsEventsFilterPostBody } from "@/api/zod/events/events";

const buildFilterFromSearchParams = (searchParams: z.infer<typeof readEventsEventsFilterPostBody>): components["schemas"]["Body_read_events_events_filter_post"] => {
	return {
		limit: searchParams.limit,
	}
}

export const Route = createFileRoute("/events")({
	component: RouteComponent,
	validateSearch: zodValidator(readEventsEventsFilterPostBody),
	loaderDeps: ({search}) => buildFilterFromSearchParams(search),
	loader: async ({context, deps}) => {
		return await context.queryClient.ensureQueryData(
			$api.queryOptions("post", "/events/filter", {
				body: deps
			})
		);
	},
});

function RouteComponent() {
	return "🚧🚧 Pardon our dust! 🚧🚧";
}
