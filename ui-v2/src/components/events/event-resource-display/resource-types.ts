import type { IconId } from "@/components/ui/icons";

export type ResourceType =
	| "flow-run"
	| "task-run"
	| "deployment"
	| "flow"
	| "work-pool"
	| "work-queue"
	| "automation"
	| "block-document"
	| "concurrency-limit"
	| "unknown";

export const RESOURCE_ICONS: Record<ResourceType, IconId> = {
	"flow-run": "Play",
	"task-run": "Cog",
	deployment: "Rocket",
	flow: "Workflow",
	"work-pool": "Server",
	"work-queue": "ListOrdered",
	automation: "Zap",
	"block-document": "Box",
	"concurrency-limit": "Gauge",
	unknown: "Circle",
};

export const RESOURCE_TYPE_LABELS: Record<ResourceType, string> = {
	"flow-run": "Flow run",
	"task-run": "Task run",
	flow: "Flow",
	deployment: "Deployment",
	"work-pool": "Work pool",
	"work-queue": "Work queue",
	automation: "Automation",
	"block-document": "Block document",
	"concurrency-limit": "Concurrency limit",
	unknown: "Resource",
};

/**
 * Parses a Prefect resource ID to determine its type.
 * Resource IDs follow the format: prefect.{resource-type}.{uuid}
 *
 * @param resourceId - The full resource ID string (e.g., "prefect.flow-run.abc-123")
 * @returns The parsed ResourceType, or "unknown" if the format is unrecognized
 */
export function parseResourceType(resourceId: string): ResourceType {
	if (!resourceId || typeof resourceId !== "string") {
		return "unknown";
	}

	if (resourceId.startsWith("prefect.flow-run.")) {
		return "flow-run";
	}
	if (resourceId.startsWith("prefect.task-run.")) {
		return "task-run";
	}
	if (resourceId.startsWith("prefect.deployment.")) {
		return "deployment";
	}
	if (resourceId.startsWith("prefect.flow.")) {
		return "flow";
	}
	if (resourceId.startsWith("prefect.work-pool.")) {
		return "work-pool";
	}
	if (resourceId.startsWith("prefect.work-queue.")) {
		return "work-queue";
	}
	if (resourceId.startsWith("prefect.automation.")) {
		return "automation";
	}
	if (resourceId.startsWith("prefect.block-document.")) {
		return "block-document";
	}
	if (resourceId.startsWith("prefect.concurrency-limit.")) {
		return "concurrency-limit";
	}

	return "unknown";
}

/**
 * Extracts the resource identifier from a Prefect resource ID.
 * Resource IDs follow the format: prefect.{resource-type}.{uuid}
 *
 * @param prefectResourceId - The full resource ID string (e.g., "prefect.flow-run.abc-123")
 * @returns The extracted ID portion (e.g., "abc-123"), or null if the format is invalid
 */
export function extractResourceId(prefectResourceId: string): string | null {
	if (!prefectResourceId || typeof prefectResourceId !== "string") {
		return null;
	}

	const parts = prefectResourceId.split(".");
	if (parts.length < 3) {
		return null;
	}

	// Join parts after index 1 (skip "prefect" and resource type)
	return parts.slice(2).join(".");
}
