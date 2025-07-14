import { toast } from "sonner";
import type { DeploymentSchedule } from "@/api/deployments";
import { useUpdateDeploymentSchedule } from "@/api/deployments";
import { Switch } from "@/components/ui/switch";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { getScheduleTitle } from "./get-schedule-title";

type ScheduleToggleSwitchProps = {
	deploymentSchedule: DeploymentSchedule;
	disabled?: boolean;
};

export const ScheduleToggleSwitch = ({
	deploymentSchedule,
	disabled,
}: ScheduleToggleSwitchProps) => {
	const { updateDeploymentSchedule } = useUpdateDeploymentSchedule();

	const handleCheckedChanged = (checked: boolean) => {
		const { id, deployment_id } = deploymentSchedule;
		if (!deployment_id) {
			throw new Error("'deployment_id' expected");
		}
		updateDeploymentSchedule(
			{ schedule_id: id, deployment_id, active: checked },
			{
				onSuccess: () =>
					toast.success(`Deployment schedule ${checked ? "active" : "paused"}`),
				onError: (error) => {
					const message =
						error.message ||
						"Unknown error while updating deployment schedule.";
					console.error(message);
				},
			},
		);
	};

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger asChild>
					<div>
						<Switch
							aria-label={`toggle ${getScheduleTitle(deploymentSchedule)}`}
							checked={deploymentSchedule.active}
							onCheckedChange={handleCheckedChanged}
							disabled={disabled}
						/>
					</div>
				</TooltipTrigger>
				{disabled && (
					<TooltipContent>Pause or resume this schedule</TooltipContent>
				)}
			</Tooltip>
		</TooltipProvider>
	);
};
