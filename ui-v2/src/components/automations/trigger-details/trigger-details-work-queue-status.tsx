import { useSuspenseQueries } from "@tanstack/react-query";
import { Suspense } from "react";
import { buildGetWorkQueueQuery } from "@/api/work-queues";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkPoolLink } from "@/components/work-pools/work-pool-link";
import { WorkQueueIconText } from "@/components/work-pools/work-queue-icon-text";
import { pluralize } from "@/utils";
import { secondsToString } from "@/utils/seconds";
import {
	type AutomationTriggerEventPosture,
	getAutomationTriggerEventPostureLabel,
	getWorkQueueStatusLabel,
	type WorkQueueStatusTriggerStatus,
} from "./trigger-utils";

export type TriggerDetailsWorkQueueStatusProps = {
	workQueueIds: string[];
	workPoolNames: string[];
	posture: AutomationTriggerEventPosture;
	status: WorkQueueStatusTriggerStatus;
	time?: number;
};

export const TriggerDetailsWorkQueueStatus = (
	props: TriggerDetailsWorkQueueStatusProps,
) => {
	return (
		<Suspense fallback={<Skeleton className="h-4 w-full" />}>
			<TriggerDetailsWorkQueueStatusImplementation {...props} />
		</Suspense>
	);
};

const TriggerDetailsWorkQueueStatusImplementation = ({
	workQueueIds,
	workPoolNames,
	posture,
	status,
	time,
}: TriggerDetailsWorkQueueStatusProps) => {
	const anyWorkQueue = workQueueIds.length === 0;
	const anyWorkPool = workPoolNames.length === 0;

	const workQueueQueries = useSuspenseQueries({
		queries: workQueueIds.map((id) => buildGetWorkQueueQuery(id)),
	});

	const workQueues = workQueueQueries.map((query) => query.data);

	return (
		<div className="flex flex-wrap gap-1 items-center text-sm">
			<span>When</span>

			{anyWorkQueue ? (
				<span>any work queue</span>
			) : (
				<>
					<span>{pluralize(workQueues.length, "work queue")}</span>
					{workQueues.map((workQueue, index) => (
						<span key={workQueue.id} className="flex items-center gap-1">
							<WorkQueueIconText
								workPoolName={workQueue.work_pool_name ?? ""}
								workQueueName={workQueue.name}
								showLabel
								showStatus
							/>
							{index === workQueues.length - 2 && <span>or</span>}
						</span>
					))}
				</>
			)}

			{!anyWorkPool && (
				<>
					<span>from the {pluralize(workPoolNames.length, "work pool")}</span>
					{workPoolNames.map((workPoolName, index) => (
						<span key={workPoolName} className="flex items-center gap-1">
							<WorkPoolLink workPoolName={workPoolName} />
							{index === workPoolNames.length - 2 && <span>or</span>}
						</span>
					))}
				</>
			)}

			<span>{getAutomationTriggerEventPostureLabel(posture)}</span>
			<span>{getWorkQueueStatusLabel(status).toLowerCase()}</span>

			{posture === "Proactive" && time !== undefined && (
				<span>for {secondsToString(time)}</span>
			)}
		</div>
	);
};
