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

function getResourceRole(resource: Record<string, string>): string | null {
	return resource["prefect.resource.role"] || null;
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
	const occurredFormatted = format(
		new Date(event.occurred),
		"yyyy/MM/dd hh:mm:ss a",
	);

	const relatedResources = event.related.filter((resource) => {
		const role = getResourceRole(resource);
		return role !== "tag";
	});

	const tags = event.related.filter((resource) => {
		const role = getResourceRole(resource);
		return role === "tag";
	});

	return (
		<div className="flex flex-col gap-4">
			<KeyValue label="Event">{eventLabel}</KeyValue>

			<KeyValue label="Occurred">{occurredFormatted}</KeyValue>

			<EventResourceDisplay event={event} />

			{(relatedResources.length > 0 || tags.length > 0) && (
				<KeyValue label="Related Resources">
					<div className="flex flex-col gap-2">
						{relatedResources.map((resource) => {
							const resourceId = getResourceId(resource);
							const resourceName = getResourceName(resource);
							const resourceType = parseResourceType(resourceId);
							const iconId = RESOURCE_ICONS[resourceType];
							const typeLabel = RESOURCE_TYPE_LABELS[resourceType];

							const displayText =
								resourceName || resourceId.split(".").pop() || resourceId;

							return (
								<div key={resourceId} className="flex items-center gap-2">
									{typeLabel && <span>{typeLabel}</span>}
									<Icon id={iconId} className="h-4 w-4 text-muted-foreground" />
									<span>{displayText}</span>
								</div>
							);
						})}

						{tags.length > 0 && (
							<div className="flex flex-wrap items-center gap-2">
								<span>Tags</span>
								{tags.map((resource) => {
									const resourceId = getResourceId(resource);
									const tagName = resourceId.split(".").pop() || resourceId;

									return (
										<Badge key={resourceId} variant="secondary">
											{tagName}
										</Badge>
									);
								})}
							</div>
						)}
					</div>
				</KeyValue>
			)}
		</div>
	);
}
