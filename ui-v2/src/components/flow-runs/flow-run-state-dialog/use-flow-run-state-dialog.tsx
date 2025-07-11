import { useState } from "react";
import { toast } from "sonner";
import type { FlowRun } from "@/api/flow-runs";
import { useSetFlowRunState } from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import type { RunStateFormValues } from "@/components/ui/run-state-change-dialog";
import { StateBadge } from "@/components/ui/state-badge";

export const useFlowRunStateDialog = (flowRun: FlowRun) => {
	const [open, setOpen] = useState(false);
	const { mutateAsync: setFlowRunState } = useSetFlowRunState();

	const handleSubmitChange = async (values: RunStateFormValues) => {
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
				},
			},
		);
	};

	const openDialog = () => {
		setOpen(true);
	};

	return {
		dialogProps: {
			currentState: {
				type: flowRun.state_type,
				name: flowRun.state_name,
			},
			open,
			onOpenChange: setOpen,
			title: "Change Flow Run State",
			onSubmitChange: handleSubmitChange,
		},
		openDialog,
	};
};
