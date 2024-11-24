import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { useToast } from "@/hooks/use-toast";
import { useMutation, useQueryClient } from "@tanstack/react-query";

type UseCreateVariableProps = {
	onSuccess: () => void;
	onError: (error: Error) => void;
};

export const useCreateVariable = ({
	onSuccess,
	onError,
}: UseCreateVariableProps) => {
	const queryClient = useQueryClient();
	const { toast } = useToast();

	return useMutation({
		mutationFn: (variable: components["schemas"]["VariableCreate"]) => {
			return getQueryService().POST("/variables/", {
				body: variable,
			});
		},
		onSettled: async () => {
			return await Promise.all([
				queryClient.invalidateQueries({
					predicate: (query) => query.queryKey[0] === "variables",
				}),
				queryClient.invalidateQueries({
					predicate: (query) => query.queryKey[0] === "total-variable-count",
				}),
			]);
		},
		onSuccess: () => {
			toast({
				title: "Variable created",
			});
			onSuccess();
		},
		onError,
	});
};

type UseUpdateVariableProps = {
	onSuccess: () => void;
	onError: (error: Error) => void;
};

type VariableUpdateWithId = components["schemas"]["VariableUpdate"] & {
	id: string;
};

export const useUpdateVariable = ({
	onSuccess,
	onError,
}: UseUpdateVariableProps) => {
	const queryClient = useQueryClient();
	const { toast } = useToast();

	return useMutation({
		mutationFn: (variable: VariableUpdateWithId) => {
			const { id, ...body } = variable;
			return getQueryService().PATCH("/variables/{id}", {
				params: { path: { id } },
				body,
			});
		},
		onSettled: async () => {
			return await Promise.all([
				queryClient.invalidateQueries({
					predicate: (query) => query.queryKey[0] === "variables",
				}),
				queryClient.invalidateQueries({
					predicate: (query) => query.queryKey[0] === "total-variable-count",
				}),
			]);
		},
		onSuccess: () => {
			toast({
				title: "Variable updated",
			});
			onSuccess();
		},
		onError,
	});
};
