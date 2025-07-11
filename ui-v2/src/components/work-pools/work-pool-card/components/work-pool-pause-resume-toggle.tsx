import { useMemo, useState } from "react";
import { toast } from "sonner";
import type { WorkPool } from "@/api/work-pools";
import { usePauseWorkPool, useResumeWorkPool } from "@/api/work-pools";
import { Switch } from "@/components/ui/switch";
export type WorkPoolPauseResumeToggleParams = {
	workPool: WorkPool;
};

export const WorkPoolPauseResumeToggle = ({
	workPool,
}: WorkPoolPauseResumeToggleParams) => {
	const [isPaused, setIsPaused] = useState(workPool.status === "PAUSED");

	const { pauseWorkPool, isPending: isPausing } = usePauseWorkPool();
	const { resumeWorkPool, isPending: isResuming } = useResumeWorkPool();

	const disabled = useMemo(() => {
		return isPausing || isResuming;
	}, [isPausing, isResuming]);

	const handleTogglePause = () => {
		if (isPaused) {
			resumeWorkPool(workPool.name, {
				onSuccess: () => {
					setIsPaused(false);
					toast.success(`${workPool.name} resumed`);
				},
				onError: () => {
					toast.error(`Failed to resume ${workPool.name}`);
				},
			});
		} else {
			pauseWorkPool(workPool.name, {
				onSuccess: () => {
					setIsPaused(true);
					toast.success(`${workPool.name} paused`);
				},
				onError: () => {
					toast.error(`Failed to pause ${workPool.name}`);
				},
			});
		}
	};

	return (
		<span className="flex items-center gap-2">
			<span className="text-sm text-muted-foreground">
				{isPaused ? "Paused" : "Active"}
			</span>
			<Switch
				checked={!isPaused}
				onCheckedChange={handleTogglePause}
				disabled={disabled}
				aria-label={isPaused ? "Resume work pool" : "Pause work pool"}
			/>
		</span>
	);
};
