import { Card } from "@/components/ui/card";
import { Typography } from "@/components/ui/typography";

import { getScheduleTitle } from "./get-schedule-title";
import { ScheduleActionMenu } from "./schedule-action-menu";
import { ScheduleToggleSwitch } from "./schedule-toggle-switch";
import type { DeploymentSchedule } from "./types";

type DeploymentScheduleItemProps = {
	deploymentSchedule: DeploymentSchedule;
};

export const DeploymentScheduleItem = ({
	deploymentSchedule,
}: DeploymentScheduleItemProps) => {
	return (
		<Card className="p-3 flex items-center justify-between">
			<Typography>{getScheduleTitle(deploymentSchedule)}</Typography>
			<div className="flex items-center gap-2">
				<ScheduleToggleSwitch deploymentSchedule={deploymentSchedule} />
				<ScheduleActionMenu deploymentSchedule={deploymentSchedule} />
			</div>
		</Card>
	);
};
