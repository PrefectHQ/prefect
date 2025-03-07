import { WorkPool } from "@/api/work-pools";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { Switch } from "@/components/ui/switch";
import { usePauseWorkPool, useResumeWorkPool } from "@/hooks/work-pools";
import { useState } from "react";
import { WorkPoolName } from "./components/work-pool-name";
import { WorkPoolTypeBadge } from "./components/work-pool-type-badge";

type WorkPoolCardProps = {
	workPool: WorkPool;
};

export const WorkPoolCard = ({ workPool }: WorkPoolCardProps) => {
	const [isPaused, setIsPaused] = useState(workPool.status === "PAUSED");

	const pauseWorkPoolMutation = usePauseWorkPool();
	const resumeWorkPoolMutation = useResumeWorkPool();

	const isUpdating =
		pauseWorkPoolMutation.isPending || resumeWorkPoolMutation.isPending;

	const handleTogglePause = () => {
		if (isPaused) {
			resumeWorkPoolMutation.mutate(workPool.name, {
				onSuccess: () => setIsPaused(false),
			});
		} else {
			pauseWorkPoolMutation.mutate(workPool.name, {
				onSuccess: () => setIsPaused(true),
			});
		}
	};

	return (
		<Card className="gap-2">
			<CardHeader className="flex flex-row items-center justify-between">
				<CardTitle className="flex items-center gap-2">
					<WorkPoolName workPoolName={workPool.name} />
					{workPool.status && <StatusBadge status={workPool.status} />}
				</CardTitle>
				<div className="flex items-center gap-2">
					<span className="text-sm text-muted-foreground">
						{isPaused ? "Paused" : "Active"}
					</span>
					<Switch
						checked={!isPaused}
						onCheckedChange={handleTogglePause}
						disabled={isUpdating}
						aria-label={isPaused ? "Resume work pool" : "Pause work pool"}
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
