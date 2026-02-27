import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildGetEventQuery } from "@/api/events";
import { EventDetailsPage } from "@/components/events/event-details-page";
import { Skeleton } from "@/components/ui/skeleton";

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
	wrapInSuspense: true,
	pendingComponent: function EventDetailPageSkeleton() {
		return (
			<div className="flex flex-col gap-6">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-2">
						<Skeleton className="h-6 w-24" />
						<Skeleton className="h-4 w-4" />
						<Skeleton className="h-6 w-48" />
					</div>
					<Skeleton className="h-8 w-8" />
				</div>
				<div className="rounded-lg border p-4 flex flex-col gap-4">
					<div className="flex gap-2">
						<Skeleton className="h-9 w-20" />
						<Skeleton className="h-9 w-16" />
					</div>
					<div className="flex flex-col gap-3">
						<div className="flex items-center gap-4 py-2">
							<Skeleton className="h-4 w-24" />
							<Skeleton className="h-4 w-48 ml-4" />
						</div>
						<div className="flex items-center gap-4 py-2">
							<Skeleton className="h-4 w-24" />
							<Skeleton className="h-4 w-36 ml-4" />
						</div>
						<div className="flex items-center gap-4 py-2">
							<Skeleton className="h-4 w-24" />
							<Skeleton className="h-4 w-56 ml-4" />
						</div>
						<div className="flex items-center gap-4 py-2">
							<Skeleton className="h-4 w-24" />
							<Skeleton className="h-4 w-40 ml-4" />
						</div>
					</div>
				</div>
			</div>
		);
	},
});
