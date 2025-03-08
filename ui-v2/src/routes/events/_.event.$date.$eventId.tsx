import { createFileRoute } from "@tanstack/react-router";
import { getQueryHooks } from "@/api/query";
import { addDays, formatISO } from "date-fns";
import { EventsDetail } from "@/components/events/events-detail";

export const Route = createFileRoute("/events/_/event/$date/$eventId")({
	component: RouteComponent,
	loader: async ({ context, params }) => {
		return await context.queryClient.ensureQueryData(
			getQueryHooks().queryOptions("post", "/events/filter", {
				body: {
					limit: 1,
					filter: {
						id: {id: [params.eventId]},
						order: "DESC",
						occurred: {
							since: formatISO(params.date, {'representation': 'date'}),
							until: formatISO(addDays(params.date, 3), {'representation': 'date'}),
						}
					}
				}
			}),
		);
	},
});

function RouteComponent() {
	const { events: [ event ] } = Route.useLoaderData()
	return <EventsDetail event={event} />
}