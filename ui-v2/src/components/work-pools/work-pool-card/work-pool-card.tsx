import { toast } from "sonner";
import type { WorkPool } from "@/api/work-pools";
import { useDeleteWorkPool } from "@/api/work-pools";
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
	const { deleteWorkPool } = useDeleteWorkPool();

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
	return (
		<Card className="gap-2">
			<CardHeader className="flex flex-row items-center justify-between">
				<CardTitle className="flex items-center gap-2">
					<WorkPoolName workPoolName={workPool.name} />
					{workPool.status && <StatusBadge status={workPool.status} />}
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
