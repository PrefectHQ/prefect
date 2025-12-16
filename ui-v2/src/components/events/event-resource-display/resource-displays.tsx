import { useSuspenseQuery } from "@tanstack/react-query";
import { buildGetAutomationQuery } from "@/api/automations";
import { buildGetBlockDocumentQuery } from "@/api/block-documents";
import { buildDeploymentDetailsQuery } from "@/api/deployments";
import { buildGetFlowRunDetailsQuery } from "@/api/flow-runs";
import { buildFLowDetailsQuery } from "@/api/flows";
import { buildGetConcurrencyLimitQuery } from "@/api/task-run-concurrency-limits";
import { buildGetTaskRunDetailsQuery } from "@/api/task-runs";
import { buildGetWorkPoolQuery } from "@/api/work-pools";
import { buildGetWorkQueueQuery } from "@/api/work-queues";
import { ResourceDisplayWithIcon } from "./event-resource-display";

type ResourceDisplayProps = {
	resourceId: string;
	className?: string;
};

export function FlowRunResourceDisplay({
	resourceId,
	className,
}: ResourceDisplayProps) {
	const { data: flowRun } = useSuspenseQuery(
		buildGetFlowRunDetailsQuery(resourceId),
	);
	return (
		<ResourceDisplayWithIcon
			resourceType="flow-run"
			displayText={flowRun.name ?? resourceId}
			className={className}
		/>
	);
}

export function TaskRunResourceDisplay({
	resourceId,
	className,
}: ResourceDisplayProps) {
	const { data: taskRun } = useSuspenseQuery(
		buildGetTaskRunDetailsQuery(resourceId),
	);
	return (
		<ResourceDisplayWithIcon
			resourceType="task-run"
			displayText={taskRun.name ?? resourceId}
			className={className}
		/>
	);
}

export function DeploymentResourceDisplay({
	resourceId,
	className,
}: ResourceDisplayProps) {
	const { data: deployment } = useSuspenseQuery(
		buildDeploymentDetailsQuery(resourceId),
	);
	return (
		<ResourceDisplayWithIcon
			resourceType="deployment"
			displayText={deployment.name}
			className={className}
		/>
	);
}

export function FlowResourceDisplay({
	resourceId,
	className,
}: ResourceDisplayProps) {
	const { data: flow } = useSuspenseQuery(buildFLowDetailsQuery(resourceId));
	return (
		<ResourceDisplayWithIcon
			resourceType="flow"
			displayText={flow.name}
			className={className}
		/>
	);
}

export function WorkPoolResourceDisplay({
	resourceId,
	className,
}: ResourceDisplayProps) {
	const { data: workPool } = useSuspenseQuery(
		buildGetWorkPoolQuery(resourceId),
	);
	return (
		<ResourceDisplayWithIcon
			resourceType="work-pool"
			displayText={workPool.name}
			className={className}
		/>
	);
}

export function WorkQueueResourceDisplay({
	resourceId,
	className,
}: ResourceDisplayProps) {
	const { data: workQueue } = useSuspenseQuery(
		buildGetWorkQueueQuery(resourceId),
	);
	return (
		<ResourceDisplayWithIcon
			resourceType="work-queue"
			displayText={workQueue.name}
			className={className}
		/>
	);
}

export function AutomationResourceDisplay({
	resourceId,
	className,
}: ResourceDisplayProps) {
	const { data: automation } = useSuspenseQuery(
		buildGetAutomationQuery(resourceId),
	);
	return (
		<ResourceDisplayWithIcon
			resourceType="automation"
			displayText={automation.name}
			className={className}
		/>
	);
}

export function BlockDocumentResourceDisplay({
	resourceId,
	className,
}: ResourceDisplayProps) {
	const { data: blockDocument } = useSuspenseQuery(
		buildGetBlockDocumentQuery(resourceId),
	);
	return (
		<ResourceDisplayWithIcon
			resourceType="block-document"
			displayText={blockDocument.name ?? resourceId}
			className={className}
		/>
	);
}

export function ConcurrencyLimitResourceDisplay({
	resourceId,
	className,
}: ResourceDisplayProps) {
	const { data: concurrencyLimit } = useSuspenseQuery(
		buildGetConcurrencyLimitQuery(resourceId),
	);
	return (
		<ResourceDisplayWithIcon
			resourceType="concurrency-limit"
			displayText={concurrencyLimit.tag ?? resourceId}
			className={className}
		/>
	);
}
