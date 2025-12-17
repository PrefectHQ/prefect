import { format } from "date-fns";
import type { Event } from "@/api/events";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icons";
import {
	EventResourceDisplay,
	EventResourceLink,
} from "../event-resource-display";
import {
	parseResourceType,
	RESOURCE_ICONS,
	RESOURCE_TYPE_LABELS,
} from "../event-resource-display/resource-types";

type EventDetailsDisplayProps = {
	event: Event;
};

const FieldLabel = ({ children }: { children: React.ReactNode }) => (
	<dt className="text-sm font-medium">{children}</dt>
);

const FieldValue = ({ children }: { children: React.ReactNode }) => (
	<dd className="text-sm">{children}</dd>
);

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
	const occurredFormatted = format(
		new Date(event.occurred),
		"yyyy/MM/dd hh:mm:ss a",
	);

	const relatedResources = (event.related ?? []).filter((resource) => {
		const role = getResourceRole(resource);
		return role !== "tag";
	});

	const tags = (event.related ?? []).filter((resource) => {
		const role = getResourceRole(resource);
		return role === "tag";
	});

	return (
		<div className="flex flex-col gap-4">
			<dl>
				<FieldLabel>Event</FieldLabel>
				<FieldValue>{event.event}</FieldValue>
			</dl>

			<dl>
				<FieldLabel>Occurred</FieldLabel>
				<FieldValue>{occurredFormatted}</FieldValue>
			</dl>

			<EventResourceDisplay event={event} />

			{(relatedResources.length > 0 || tags.length > 0) && (
				<dl>
					<FieldLabel>Related Resources</FieldLabel>
					<dd className="flex flex-col gap-2 text-sm">
						{relatedResources.map((resource) => {
							const resourceId = getResourceId(resource);
							const resourceName = getResourceName(resource);
							const resourceType = parseResourceType(resourceId);
							const iconId = RESOURCE_ICONS[resourceType];
							const typeLabel = RESOURCE_TYPE_LABELS[resourceType];

							const displayText =
								resourceName || resourceId.split(".").pop() || resourceId;

							return (
								<EventResourceLink
									key={resourceId}
									resource={resource}
									relatedResources={event.related ?? []}
									className="flex items-center gap-2 hover:underline"
								>
									{typeLabel && <span>{typeLabel}</span>}
									<Icon id={iconId} className="h-4 w-4 text-muted-foreground" />
									<span>{displayText}</span>
								</EventResourceLink>
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
					</dd>
				</dl>
			)}
		</div>
	);
}
