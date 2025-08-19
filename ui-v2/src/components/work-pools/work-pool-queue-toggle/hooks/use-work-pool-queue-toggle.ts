import { useCallback } from "react";
import { toast } from "sonner";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import {
	usePauseWorkPoolQueueMutation,
	useResumeWorkPoolQueueMutation,
} from "@/api/work-pool-queues";

export const useWorkPoolQueueToggle = (
	queue: WorkPoolQueue,
	onUpdate?: () => void,
) => {
	const pauseMutation = usePauseWorkPoolQueueMutation();
	const resumeMutation = useResumeWorkPoolQueueMutation();

	const handleToggle = useCallback(
		(isResumed: boolean) => {
			if (!queue.work_pool_name) {
				toast.error("Work pool name is required");
				return;
			}

			const mutation = isResumed ? resumeMutation : pauseMutation;
			const action = isResumed ? "resumed" : "paused";

			mutation.mutate(
				{ workPoolName: queue.work_pool_name, queueName: queue.name },
				{
					onSuccess: () => {
						toast.success(`Queue ${action} successfully`);
						onUpdate?.();
					},
					onError: () => {
						toast.error(`Failed to ${action.slice(0, -1)} queue`);
					},
				},
			);
		},
		[queue, pauseMutation, resumeMutation, onUpdate],
	);

	return {
		handleToggle,
		isLoading: pauseMutation.isPending || resumeMutation.isPending,
	};
};
