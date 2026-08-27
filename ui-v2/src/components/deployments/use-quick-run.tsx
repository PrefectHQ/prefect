import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import type { Deployment } from "@/api/deployments";
import { useDeploymentCreateFlowRun } from "@/api/flow-runs";
import { Button } from "@/components/ui/button";

const DEPLOYMENT_QUICK_RUN_PAYLOAD = {
	state: {
		type: "SCHEDULED",
		message: "Run from the Prefect UI with defaults",
		state_details: {
			deferred: false,
			untrackable_result: false,
			pause_reschedule: false,
		},
	},
} as const;

/**
 *
 * @returns a function that handles the mutation and UX when a deployment creates a quick run
 */
export const useQuickRun = (deployment: Deployment) => {
	const { createDeploymentFlowRun, isPending } = useDeploymentCreateFlowRun();
	const [isParametersDialogOpen, setIsParametersDialogOpen] = useState(false);
	const requiredParameters = deployment.parameter_openapi_schema?.required;
	const hasRequiredParameters =
		Array.isArray(requiredParameters) && requiredParameters.length > 0;

	const onQuickRun = () => {
		if (hasRequiredParameters) {
			setIsParametersDialogOpen(true);
			return;
		}

		createDeploymentFlowRun(
			{
				id: deployment.id,
				...DEPLOYMENT_QUICK_RUN_PAYLOAD,
			},
			{
				onSuccess: (res) => {
					toast.success("Flow run created", {
						action: (
							<Link to="/runs/flow-run/$id" params={{ id: res.id }}>
								<Button size="sm">View run</Button>
							</Link>
						),
						description: (
							<p>
								<span className="font-bold">{res.name}</span> scheduled to start{" "}
								<span className="font-bold">now</span>
							</p>
						),
					});
				},
				onError: (error) => {
					const message =
						error.message || "Unknown error while creating flow run.";
					toast.error(message);
				},
			},
		);
	};

	return {
		onQuickRun,
		isPending,
		parametersDialogState: {
			open: isParametersDialogOpen,
			onOpenChange: setIsParametersDialogOpen,
		},
	};
};
