import { toast } from "sonner";
import { type Deployment, useUpdateDeployment } from "@/api/deployments";
import { Switch } from "@/components/ui/switch";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";

type DeploymentScheduleToggleProps = {
	deployment: Deployment;
};

export const DeploymentScheduleToggle = ({
	deployment,
}: DeploymentScheduleToggleProps) => {
	const { updateDeployment } = useUpdateDeployment();

	const handleChckedChange = (checked: boolean) => {
		updateDeployment(
			{ id: deployment.id, paused: !checked },
			{
				onSuccess: () => {
					toast.success(`Deployment ${checked ? "active" : "paused"}`);
				},
				onError: (error) => {
					const message =
						error.message || "Unknown error while updating deployment";
					console.error(message);
				},
			},
		);
	};

	const isDeploymentDeprecated =
		deployment.entrypoint === "" || deployment.entrypoint === null;

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger asChild>
					<div>
						<Switch
							aria-label="Pause or resume all schedules"
							disabled={isDeploymentDeprecated}
							onCheckedChange={handleChckedChange}
							checked={!deployment.paused}
						/>
					</div>
				</TooltipTrigger>
				<TooltipContent>Pause or resume all schedules</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};
