import { getQueryService } from "@/api/service";
import { queryKeyFactory } from "@/api/work-pools/work-pools";
import { useMutation, useQueryClient } from "@tanstack/react-query";

/**
 * Hook for pausing a work pool
 * @returns Mutation for pausing a work pool
 */
export const usePauseWorkPool = () => {
	const queryClient = useQueryClient();

	const { mutate: pauseWorkPool, ...rest } = useMutation({
		mutationFn: (name: string) =>
			getQueryService().PATCH("/work_pools/{name}", {
				params: { path: { name } },
				body: {
					is_paused: true,
				},
			}),
		onSettled: () =>
			queryClient.invalidateQueries({
				queryKey: queryKeyFactory.all(),
			}),
	});
	return { pauseWorkPool, ...rest };
};

/**
 * Hook for resuming a work pool
 * @returns Mutation for resuming a work pool
 */
export const useResumeWorkPool = () => {
	const queryClient = useQueryClient();

	const { mutate: resumeWorkPool, ...rest } = useMutation({
		mutationFn: (name: string) =>
			getQueryService().PATCH("/work_pools/{name}", {
				params: { path: { name } },
				body: {
					is_paused: false,
				},
			}),
		onSettled: () =>
			queryClient.invalidateQueries({
				queryKey: queryKeyFactory.all(),
			}),
	});

	return { resumeWorkPool, ...rest };
};

/**
 * Hook for deleting a work pool
 * @returns Mutation for deleting a work pool
 */
export const useDeleteWorkPool = () => {
	const queryClient = useQueryClient();

	const { mutate: deleteWorkPool, ...rest } = useMutation({
		mutationFn: (name: string) =>
			getQueryService().DELETE("/work_pools/{name}", {
				params: { path: { name } },
			}),
		onSettled: () =>
			queryClient.invalidateQueries({
				queryKey: queryKeyFactory.all(),
			}),
	});

	return { deleteWorkPool, ...rest };
};
