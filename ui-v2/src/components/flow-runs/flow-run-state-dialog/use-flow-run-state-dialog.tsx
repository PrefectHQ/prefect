import type { FlowRun } from "@/api/flow-runs";
import { useSetFlowRunState } from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import type { RunStateFormValues } from "@/components/ui/run-state-change-dialog";
import { StateBadge } from "@/components/ui/state-badge";
import { RUN_STATES } from "@/utils/states";
import { useCallback, useState } from "react";
import { toast } from "sonner";

export const useFlowRunStateDialog = () => {
	const [open, setOpen] = useState(false);
	const [flowRun, setFlowRun] = useState<FlowRun | null>(null);
	const { mutateAsync: setFlowRunState } = useSetFlowRunState();

	const handleSubmitChange = async (values: RunStateFormValues) => {
		if (!flowRun?.id) {
			return;
		}

		await setFlowRunState(
			{
				id: flowRun.id,
				state: {
					type: values.state as components["schemas"]["StateType"],
					message: values.message || null,
				},
				force: true,
			},
			{
				onSuccess: () => {
					toast.success(
						<div className="flex items-center gap-2">
							Flow run state changed to{" "}
							<StateBadge
								type={values.state as components["schemas"]["StateType"]}
								name={values.state}
							/>
						</div>,
					);
				},
				onError: (error: Error) => {
					const message =
						error.message || "Unknown error while changing flow run state.";
					toast.error(message);
					throw error;
				},
			},
		);
	};

	const openDialog = useCallback((run: FlowRun) => {
		setFlowRun(run);
		setOpen(true);
	}, []);

	return {
		dialogProps: flowRun?.state
			? {
					currentState: {
						id: flowRun.state.id,
						type: flowRun.state.type,
						name: flowRun.state.name ?? RUN_STATES[flowRun.state.type],
						message: flowRun.state.message,
					},
					open,
					onOpenChange: setOpen,
					title: "Change Flow Run State",
					onSubmitChange: handleSubmitChange,
				}
			: null,
		openDialog,
	};
};
