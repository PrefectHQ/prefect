import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { buildFilterWorkPoolsQuery, type WorkPool } from "@/api/work-pools";
import { Icon } from "@/components/ui/icons";
import { pluralize } from "@/utils";
import { secondsToString } from "@/utils/seconds";
import type { AutomationTriggerEventPosture } from "./trigger-utils";

type WorkPoolStatusType = "READY" | "NOT_READY" | "PAUSED";

export type TriggerDetailsWorkPoolStatusProps = {
	workPoolIds: string[];
	posture: AutomationTriggerEventPosture;
	status: WorkPoolStatusType;
	time?: number;
};

const getStatusLabel = (status: WorkPoolStatusType): string => {
	switch (status) {
		case "READY":
			return "Ready";
		case "NOT_READY":
			return "Not Ready";
		case "PAUSED":
			return "Paused";
	}
};

const WorkPoolLinkInline = ({ workPoolName }: { workPoolName: string }) => {
	return (
		<Link
			to="/work-pools/work-pool/$workPoolName"
			params={{ workPoolName }}
			className="inline-flex items-center gap-1"
		>
			<Icon id="Cpu" className="size-4" />
			{workPoolName}
		</Link>
	);
};

const renderWorkPoolLinks = (workPools: WorkPool[]) => {
	if (workPools.length === 0) {
		return null;
	}

	return workPools.map((workPool, index) => (
		<span key={workPool.id} className="inline-flex items-center gap-1">
			<WorkPoolLinkInline workPoolName={workPool.name} />
			{index === workPools.length - 2 && " or "}
			{index < workPools.length - 2 && ", "}
		</span>
	));
};

export const TriggerDetailsWorkPoolStatus = ({
	workPoolIds,
	posture,
	status,
	time,
}: TriggerDetailsWorkPoolStatusProps) => {
	const { data: workPools = [] } = useQuery(
		buildFilterWorkPoolsQuery(
			{
				offset: 0,
				work_pools: { id: { any_: workPoolIds }, operator: "and_" },
			},
			{ enabled: workPoolIds.length > 0 },
		),
	);

	const postureLabel = posture === "Reactive" ? "enters" : "stays in";
	const statusLabel = getStatusLabel(status).toLowerCase();

	const workPoolLabel =
		workPoolIds.length === 0
			? "any work pool"
			: `${pluralize(workPoolIds.length, "work pool")} `;

	return (
		<div className="flex flex-wrap gap-1 items-center">
			<span>When</span>
			<span>{workPoolLabel}</span>
			{workPoolIds.length > 0 && renderWorkPoolLinks(workPools)}
			<span>{postureLabel}</span>
			<span>{statusLabel}</span>
			{posture === "Proactive" && time !== undefined && (
				<span>for {secondsToString(time)}</span>
			)}
		</div>
	);
};
