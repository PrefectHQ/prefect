import { useQuery } from "@tanstack/react-query";
import { max } from "date-fns";
import { toast } from "sonner";
import type { WorkPool } from "@/api/work-pools";
import {
	buildListWorkPoolWorkersQuery,
	useDeleteWorkPool,
} from "@/api/work-pools";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { WorkPoolStatusIcon } from "@/components/work-pools/work-pool-status-icon";
import { useNow } from "@/hooks/use-now";
import { formatDateTimeRelative } from "@/utils";
import { WorkPoolContextMenu } from "./components/work-pool-context-menu";
import { WorkPoolName } from "./components/work-pool-name";
import { WorkPoolPauseResumeToggle } from "./components/work-pool-pause-resume-toggle";
import { WorkPoolTypeBadge } from "./components/work-pool-type-badge";

type WorkPoolCardProps = {
	workPool: WorkPool;
};

export const WorkPoolCard = ({ workPool }: WorkPoolCardProps) => {
	const { deleteWorkPool } = useDeleteWorkPool();
	const now = useNow({ interval: 1000 });
	const { data: workers } = useQuery(
		buildListWorkPoolWorkersQuery(workPool.name),
	);

	const handleDelete = () => {
		deleteWorkPool(workPool.name, {
			onSuccess: () => {
				toast.success(`${workPool.name} deleted`);
			},
			onError: (error) => {
				toast.error(
					`Failed to delete work pool: ${error instanceof Error ? error.message : "Unknown error"}`,
				);
			},
		});
	};

	const lastWorkerHeartbeat =
		workers && workers.length > 0
			? max(
					workers
						.filter((worker) => worker.last_heartbeat_time)
						.map((worker) => new Date(worker.last_heartbeat_time as string)),
				)
			: null;

	const lastPolled = lastWorkerHeartbeat
		? formatDateTimeRelative(lastWorkerHeartbeat, now)
		: null;

	return (
		<Card className="gap-2">
			<CardHeader className="flex flex-row items-center justify-between">
				<CardTitle className="flex items-center gap-2">
					<WorkPoolName workPoolName={workPool.name} />
					{workPool.status && (
						<WorkPoolStatusIcon status={workPool.status} showTooltip />
					)}
				</CardTitle>
				<div className="flex items-center gap-2">
					<WorkPoolPauseResumeToggle workPool={workPool} />
					<WorkPoolContextMenu workPool={workPool} onDelete={handleDelete} />
				</div>
			</CardHeader>
			<CardContent className="flex flex-col gap-1">
				<div className="flex items-center gap-1">
					<WorkPoolTypeBadge type={workPool.type} />
				</div>
				<div className="flex flex-wrap gap-x-8 gap-y-1 text-sm">
					<div>
						<span className="font-medium text-muted-foreground">
							Concurrency Limit
						</span>{" "}
						<span className="text-foreground">
							{workPool.concurrency_limit !== null &&
							workPool.concurrency_limit !== undefined
								? workPool.concurrency_limit
								: "∞"}
						</span>
					</div>
					{lastPolled && (
						<div>
							<span className="font-medium text-muted-foreground">
								Last Polled
							</span>{" "}
							<span className="text-foreground">{lastPolled}</span>
						</div>
					)}
				</div>
			</CardContent>
		</Card>
	);
};
