import { format } from "date-fns";
import type { Event } from "@/api/events";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icons";
import { EventResourceDisplay } from "../event-resource-display";
import {
	parseResourceType,
	RESOURCE_ICONS,
	RESOURCE_TYPE_LABELS,
} from "../event-resource-display/resource-types";
import { formatEventLabel } from "../events-timeline";

type EventDetailsDisplayProps = {
	event: Event;
};

type KeyValueProps = {
	label: string;
	children: React.ReactNode;
};

function KeyValue({ label, children }: KeyValueProps) {
	return (
		<div className="flex flex-col gap-0.5">
			<span className="text-sm font-medium">{label}</span>
			<div className="text-sm">{children}</div>
		</div>
	);
}

function getResourceRole(resource: Record<string, string>): string | undefined {
	return resource["prefect.resource.role"];
}

function getResourceId(resource: Record<string, string>): string {
	return resource["prefect.resource.id"] || "";
}

function getResourceName(resource: Record<string, string>): string | null {
	return (
		resource["prefect.resource.name"] ||
		resource["prefect.name"] ||
		resource["prefect-cloud.name"] ||
		null
	);
}

export function EventDetailsDisplay({ event }: EventDetailsDisplayProps) {
	const eventLabel = formatEventLabel(event.event);
	const occurredDate = new Date(event.occurred);
	const formattedOccurred = format(occurredDate, "yyyy/MM/dd hh:mm:ss a");

	const related = event.related || [];
	const tags = related.filter((r) => getResourceRole(r) === "tag");
	const relatedResources = related.filter((r) => getResourceRole(r) !== "tag");

	return (
		<div className="flex flex-col gap-4">
			<KeyValue label="Event">{eventLabel}</KeyValue>

			<KeyValue label="Occurred">{formattedOccurred}</KeyValue>

			<EventResourceDisplay event={event} />

			{relatedResources.length > 0 && (
				<KeyValue label="Related Resources">
					<div className="flex flex-col gap-2">
						{relatedResources.map((resource) => {
							const resourceId = getResourceId(resource);
							const resourceName = getResourceName(resource);
							const displayText = resourceName || resourceId;
							const resourceType = parseResourceType(resourceId);
							const typeLabel = RESOURCE_TYPE_LABELS[resourceType];
							const iconId = RESOURCE_ICONS[resourceType];

							return (
								<div key={resourceId} className="flex items-center gap-2">
									{typeLabel && <span>{typeLabel}</span>}
									<Icon id={iconId} className="h-4 w-4 text-muted-foreground" />
									<span>{displayText}</span>
								</div>
							);
						})}
					</div>
				</KeyValue>
			)}

			{tags.length > 0 && (
				<KeyValue label="Tags">
					<div className="flex flex-wrap gap-1">
						{tags.map((tag) => {
							const tagId = getResourceId(tag);
							const tagName = getResourceName(tag) || tagId.split(".").pop();
							return (
								<Badge key={tagId} variant="secondary">
									{tagName}
								</Badge>
							);
						})}
					</div>
				</KeyValue>
			)}
		</div>
	);
}
