import type { DeploymentSchedule } from "@/api/deployments";
import { Card } from "@/components/ui/card";
import { Typography } from "@/components/ui/typography";

import { getScheduleTitle } from "./get-schedule-title";
import { ScheduleActionMenu } from "./schedule-action-menu";
import { ScheduleToggleSwitch } from "./schedule-toggle-switch";

type DeploymentScheduleItemProps = {
	deploymentSchedule: DeploymentSchedule;
	onEditSchedule: (scheduleId: string) => void;
};

export const DeploymentScheduleItem = ({
	deploymentSchedule,
	onEditSchedule,
}: DeploymentScheduleItemProps) => {
	return (
		<Card className="p-3 flex items-center justify-between">
			<Typography>{getScheduleTitle(deploymentSchedule)}</Typography>
			<div className="flex items-center gap-2">
				<ScheduleToggleSwitch deploymentSchedule={deploymentSchedule} />
				<ScheduleActionMenu
					deploymentSchedule={deploymentSchedule}
					onEditSchedule={onEditSchedule}
				/>
			</div>
		</Card>
	);
};
