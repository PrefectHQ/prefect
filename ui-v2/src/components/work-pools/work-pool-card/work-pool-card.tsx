import { WorkPool, deleteWorkPool } from "@/api/work-pools";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { WorkPoolContextMenu } from "./components/work-pool-context-menu";
import { WorkPoolName } from "./components/work-pool-name";
import { WorkPoolPauseResumeToggle } from "./components/work-pool-pause-resume-toggle";
import { WorkPoolTypeBadge } from "./components/work-pool-type-badge";

type WorkPoolCardProps = {
	workPool: WorkPool;
};

export const WorkPoolCard = ({ workPool }: WorkPoolCardProps) => {
	return (
		<Card className="gap-2">
			<CardHeader className="flex flex-row items-center justify-between">
				<CardTitle className="flex items-center gap-2">
					<WorkPoolName workPoolName={workPool.name} />
					{workPool.status && <StatusBadge status={workPool.status} />}
				</CardTitle>
				<div className="flex items-center gap-2">
					<WorkPoolPauseResumeToggle workPool={workPool} />
					<WorkPoolContextMenu
						workPool={workPool}
						onDelete={() => deleteWorkPool(workPool.name)}
					/>
				</div>
			</CardHeader>
			<CardContent className="flex flex-col gap-1">
				<div className="flex items-center gap-1">
					<WorkPoolTypeBadge type={workPool.type} />
				</div>
				<div className="text-sm text-muted-foreground">
					Concurrency:{" "}
					<span className="text-foreground">
						{workPool.concurrency_limit
							? workPool.concurrency_limit
							: "Unlimited"}
					</span>
				</div>
			</CardContent>
		</Card>
	);
};
