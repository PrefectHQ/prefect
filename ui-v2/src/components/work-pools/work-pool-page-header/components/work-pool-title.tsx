import type { WorkPool } from "@/api/work-pools";
import { WorkPoolStatusBadge } from "@/components/work-pools/work-pool-status-badge";

interface WorkPoolTitleProps {
	workPool: WorkPool;
}

export const WorkPoolTitle = ({ workPool }: WorkPoolTitleProps) => {
	return (
		<div className="flex items-center gap-2">
			<span>{workPool.name}</span>
			<WorkPoolStatusBadge
				status={
					(workPool.status?.toLowerCase() as
						| "ready"
						| "paused"
						| "not_ready") ?? "not_ready"
				}
			/>
		</div>
	);
};
