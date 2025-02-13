import { useUpdateDeploymentSchedule } from "@/api/deployments";
import type { DeploymentSchedule } from "@/api/deployments";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import { getScheduleTitle } from "./get-schedule-title";

type ScheduleToggleSwitchProps = {
	deploymentSchedule: DeploymentSchedule;
};

export const ScheduleToggleSwitch = ({
	deploymentSchedule,
}: ScheduleToggleSwitchProps) => {
	const { toast } = useToast();
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
					toast({
						title: `Deployment schedule ${checked ? "active" : "inactive"}`,
					}),
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
		<Switch
			aria-label={`toggle ${getScheduleTitle(deploymentSchedule)}`}
			checked={deploymentSchedule.active}
			onCheckedChange={handleCheckedChanged}
		/>
	);
};
