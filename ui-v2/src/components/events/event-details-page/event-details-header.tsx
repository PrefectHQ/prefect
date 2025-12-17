import type { Event } from "@/api/events";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { formatEventLabel } from "../events-timeline";

type EventDetailsHeaderProps = {
	event: Event;
};

export function EventDetailsHeader({ event }: EventDetailsHeaderProps) {
	const eventLabel = formatEventLabel(event.event);

	return (
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem>
					<BreadcrumbLink to="/events" className="text-xl font-semibold">
						Event Feed
					</BreadcrumbLink>
				</BreadcrumbItem>
				<BreadcrumbSeparator />
				<BreadcrumbItem className="text-xl font-semibold">
					<BreadcrumbPage>{eventLabel}</BreadcrumbPage>
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	);
}
