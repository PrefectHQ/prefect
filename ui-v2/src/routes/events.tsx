import { createFileRoute } from "@tanstack/react-router";
import { getQueryHooks } from "@/api/query";
import { readEventsEventsFilterPostBody } from "@/api/zod/events/events";
import { zodValidator } from "@tanstack/zod-adapter";


export const Route = createFileRoute("/events")({
	component: RouteComponent,
	validateSearch: zodValidator(readEventsEventsFilterPostBody),
	loaderDeps: ({ search }) => search,
	loader: async ({ context, deps }) => {
		return await context.queryClient.ensureQueryData(
			getQueryHooks().queryOptions("post", "/events/filter", {
				body: deps as any,
			}),
		);
	},
});

function RouteComponent() {
	return 'lol'
}
