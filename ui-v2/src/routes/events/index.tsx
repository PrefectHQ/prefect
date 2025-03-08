import { createFileRoute } from "@tanstack/react-router";
import { getQueryHooks } from "@/api/query";
import { readEventsEventsFilterPostBody } from "@/api/zod/events/events";
import { zodValidator } from "@tanstack/zod-adapter";
import { components } from "@/api/prefect";
import { Link } from "@tanstack/react-router";
import { formatISO } from "date-fns";

export const Route = createFileRoute("/events/")({
	component: RouteComponent,
	validateSearch: zodValidator(readEventsEventsFilterPostBody),
	loaderDeps: ({ search }) => search,
	loader: async ({ context, deps }) => {
		return await context.queryClient.ensureQueryData(
			getQueryHooks().queryOptions("post", "/events/filter", {
				// Note: There's a type mismatch between deps and the API schema.
				// The API expects 'resource.distinct' to be a required boolean, but our schema defines it as optional.
				// This is an idiosyncrasy between orval and openapi-ts but is fine for now.
				body: deps as components["schemas"]["Body_read_events_events_filter_post"]
			}),
		);
	},
});

function RouteComponent() {
	const data = Route.useLoaderData();
	return (
		<ul>
			{data.events.map((event) => {
				const eventDate = new Date(event.occurred);
				return (
					<li key={event.id}>
						<Link
							to="/events/event/$date/$eventId"
							params={{
								date: formatISO(eventDate, {'representation': 'date'}),
								eventId: event.id
							}}
						>
							{event.event}
						</Link>
					</li>
				);
			})}
		</ul>
	);
}