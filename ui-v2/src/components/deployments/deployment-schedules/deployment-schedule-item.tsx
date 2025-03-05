import type { DeploymentSchedule } from "@/api/deployments";
import { Card } from "@/components/ui/card";
import { Typography } from "@/components/ui/typography";

import { getScheduleTitle } from "./get-schedule-title";
import { ScheduleActionMenu } from "./schedule-action-menu";
import { ScheduleToggleSwitch } from "./schedule-toggle-switch";

type DeploymentScheduleItemProps = {
	deploymentSchedule: DeploymentSchedule;
	disabled: boolean;
	onEditSchedule: (scheduleId: string) => void;
};

export const DeploymentScheduleItem = ({
	deploymentSchedule,
	disabled,
	onEditSchedule,
}: DeploymentScheduleItemProps) => {
	return (
		<Card className="p-3">
			<div className="flex items-center justify-between gap-2">
				<Typography>{getScheduleTitle(deploymentSchedule)}</Typography>
				<div className="flex items-baseline gap-2">
					<ScheduleToggleSwitch
						deploymentSchedule={deploymentSchedule}
						disabled={disabled}
					/>
					<ScheduleActionMenu
						deploymentSchedule={deploymentSchedule}
						onEditSchedule={onEditSchedule}
					/>
				</div>
			</div>
		</Card>
	);
};
