import { useCallback } from "react";
import { toast } from "sonner";
import type { WorkPool } from "@/api/work-pools";
import { usePauseWorkPool, useResumeWorkPool } from "@/api/work-pools";

export const useWorkPoolToggle = (
	workPool: WorkPool,
	onUpdate?: () => void,
) => {
	const { pauseWorkPool, isPending: pausePending } = usePauseWorkPool();
	const { resumeWorkPool, isPending: resumePending } = useResumeWorkPool();

	const handleToggle = useCallback(
		(checked: boolean) => {
			if (checked) {
				// Switch is checked = work pool should be active (resume)
				resumeWorkPool(workPool.name, {
					onSuccess: () => {
						toast.success("Work pool resumed");
						onUpdate?.();
					},
					onError: () => {
						toast.error("Failed to resume work pool");
					},
				});
			} else {
				// Switch is unchecked = work pool should be paused
				pauseWorkPool(workPool.name, {
					onSuccess: () => {
						toast.success("Work pool paused");
						onUpdate?.();
					},
					onError: () => {
						toast.error("Failed to pause work pool");
					},
				});
			}
		},
		[workPool.name, pauseWorkPool, resumeWorkPool, onUpdate],
	);

	return {
		handleToggle,
		isLoading: pausePending || resumePending,
	};
};
