import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { categorizeError } from "@/api/error-utils";
import { buildGetEventQuery } from "@/api/events";
import { EventDetailsPage } from "@/components/events/event-details-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";

const searchParams = z.object({
	tab: z.enum(["details", "raw"]).optional().default("details"),
});

function parseRouteDate(dateStr: string): Date {
	const [year, month, day] = dateStr.split("-").map(Number);
	return new Date(year, month - 1, day);
}

export const Route = createFileRoute("/events/event/$eventDate/$eventId")({
	validateSearch: zodValidator(searchParams),
	component: function RouteComponent() {
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
	},
	loader: async ({ params, context: { queryClient } }) => {
		const eventDate = parseRouteDate(params.eventDate);
		await queryClient.ensureQueryData(
			buildGetEventQuery(params.eventId, eventDate),
		);
	},
	errorComponent: function EventDetailErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load event");
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Event</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});
