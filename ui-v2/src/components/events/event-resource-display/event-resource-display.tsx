import type { components } from "@/api/prefect";
import { cn } from "@/utils";

type Event = components["schemas"]["ReceivedEvent"];

type EventResourceDisplayProps = {
	event: Event;
	className?: string;
};

function getResourceName(resource: Record<string, string>): string | null {
	return (
		resource["prefect.resource.name"] ||
		resource["prefect.name"] ||
		resource["prefect-cloud.name"] ||
		null
	);
}

function getResourceId(resource: Record<string, string>): string {
	return resource["prefect.resource.id"] || "";
}

export function EventResourceDisplay({
	event,
	className,
}: EventResourceDisplayProps) {
	const resourceName = getResourceName(event.resource);
	const resourceId = getResourceId(event.resource);

	return (
		<div className={cn("flex flex-col gap-0.5", className)}>
			<span className="text-sm font-medium">Resource</span>
			<div className="text-sm text-muted-foreground">
				{resourceName ? (
					<span className="font-medium text-foreground">{resourceName}</span>
				) : null}
				{resourceId && (
					<span
						className={cn(
							"font-mono text-xs",
							resourceName ? "ml-2 text-muted-foreground" : "text-foreground",
						)}
					>
						{resourceId}
					</span>
				)}
			</div>
		</div>
	);
}
