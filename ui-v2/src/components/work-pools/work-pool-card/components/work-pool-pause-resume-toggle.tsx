import { WorkPool } from "@/api/work-pools";
import { Switch } from "@/components/ui/switch";
import { useResumeWorkPool } from "@/hooks/work-pools";
import { usePauseWorkPool } from "@/hooks/work-pools";
import { useMemo, useState } from "react";

export type WorkPoolPauseResumeToggleParams = {
	workPool: WorkPool;
};

export const WorkPoolPauseResumeToggle = ({
	workPool,
}: WorkPoolPauseResumeToggleParams) => {
	const [isPaused, setIsPaused] = useState(workPool.status === "PAUSED");

	const pauseWorkPoolMutation = usePauseWorkPool();
	const resumeWorkPoolMutation = useResumeWorkPool();

	const disabled = useMemo(() => {
		return pauseWorkPoolMutation.isPending || resumeWorkPoolMutation.isPending;
	}, [pauseWorkPoolMutation.isPending, resumeWorkPoolMutation.isPending]);

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
