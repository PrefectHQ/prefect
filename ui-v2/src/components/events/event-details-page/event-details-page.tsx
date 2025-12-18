import { useSuspenseQuery } from "@tanstack/react-query";
import { buildGetEventQuery } from "@/api/events";
import { Card, CardContent } from "@/components/ui/card";
import { EventActionMenu } from "./event-action-menu";
import { EventDetailsHeader } from "./event-details-header";
import { EventDetailsTabs } from "./event-details-tabs";

type EventDetailsPageProps = {
	eventId: string;
	eventDate: Date;
	defaultTab?: "details" | "raw";
	onTabChange?: (tab: string) => void;
};

export function EventDetailsPage({
	eventId,
	eventDate,
	defaultTab,
	onTabChange,
}: EventDetailsPageProps) {
	const { data: event } = useSuspenseQuery(
		buildGetEventQuery(eventId, eventDate),
	);

	return (
		<div className="flex flex-col gap-6">
			<div className="flex items-center justify-between">
				<EventDetailsHeader event={event} />
				<EventActionMenu event={event} />
			</div>
			<Card>
				<CardContent>
					<EventDetailsTabs
						event={event}
						defaultTab={defaultTab}
						onTabChange={onTabChange}
					/>
				</CardContent>
			</Card>
		</div>
	);
}
