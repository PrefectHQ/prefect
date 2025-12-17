import {
	AutomationResourceDisplay,
	BlockDocumentResourceDisplay,
	ConcurrencyLimitResourceDisplay,
	DeploymentResourceDisplay,
	FlowResourceDisplay,
	FlowRunResourceDisplay,
	TaskRunResourceDisplay,
	WorkPoolResourceDisplay,
	WorkQueueResourceDisplay,
} from "./resource-displays";
import type { ResourceType } from "./resource-types";

type ResolvedResourceDisplayProps = {
	resourceType: Exclude<ResourceType, "unknown">;
	resourceId: string;
	className?: string;
};

export function ResolvedResourceDisplay({
	resourceType,
	resourceId,
	className,
}: ResolvedResourceDisplayProps) {
	switch (resourceType) {
		case "flow-run":
			return (
				<FlowRunResourceDisplay resourceId={resourceId} className={className} />
			);
		case "task-run":
			return (
				<TaskRunResourceDisplay resourceId={resourceId} className={className} />
			);
		case "deployment":
			return (
				<DeploymentResourceDisplay
					resourceId={resourceId}
					className={className}
				/>
			);
		case "flow":
			return (
				<FlowResourceDisplay resourceId={resourceId} className={className} />
			);
		case "work-pool":
			return (
				<WorkPoolResourceDisplay
					resourceId={resourceId}
					className={className}
				/>
			);
		case "work-queue":
			return (
				<WorkQueueResourceDisplay
					resourceId={resourceId}
					className={className}
				/>
			);
		case "automation":
			return (
				<AutomationResourceDisplay
					resourceId={resourceId}
					className={className}
				/>
			);
		case "block-document":
			return (
				<BlockDocumentResourceDisplay
					resourceId={resourceId}
					className={className}
				/>
			);
		case "concurrency-limit":
			return (
				<ConcurrencyLimitResourceDisplay
					resourceId={resourceId}
					className={className}
				/>
			);
		default:
			return null;
	}
}
