import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildGetEventQuery } from "@/api/events";
import { EventDetailsPage } from "@/components/events/event-details-page";

const searchParams = z.object({
	tab: z.enum(["details", "raw"]).optional().default("details"),
});

function parseRouteDate(dateStr: string): Date {
	const [year, month, day] = dateStr.split("-").map(Number);
	return new Date(year, month - 1, day);
}

export const Route = createFileRoute("/events/event/$eventDate/$eventId")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loader: async ({ params, context: { queryClient } }) => {
		const eventDate = parseRouteDate(params.eventDate);
		await queryClient.ensureQueryData(
			buildGetEventQuery(params.eventId, eventDate),
		);
	},
	wrapInSuspense: true,
});

function RouteComponent() {
	const { eventDate, eventId } = Route.useParams();
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	const parsedDate = parseRouteDate(eventDate);

	const handleTabChange = (tab: string) => {
		void navigate({
			to: ".",
			search: { tab: tab as "details" | "raw" },
			replace: true,
		});
	};

	return (
		<EventDetailsPage
			eventId={eventId}
			eventDate={parsedDate}
			defaultTab={search.tab}
			onTabChange={handleTabChange}
		/>
	);
}
