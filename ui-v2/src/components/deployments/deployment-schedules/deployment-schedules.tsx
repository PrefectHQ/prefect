import { useMemo } from "react";
import type { Deployment } from "@/api/deployments";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";
import { DeploymentScheduleItem } from "./deployment-schedule-item";
import { DeploymentScheduleToggle } from "./deployment-schedule-toggle";

const NUM_SCHEDULES_TO_TOGGLE = 3;

type DeploymentSchedulesProps = {
	onAddSchedule: () => void;
	onEditSchedule: (scheduleId: string) => void;
	deployment: Deployment;
};

export const DeploymentSchedules = ({
	deployment,
	onAddSchedule,
	onEditSchedule,
}: DeploymentSchedulesProps) => {
	// nb: Need to sort by created, because API re-arranges order per last update
	const deploymentSchedulesSorted = useMemo(() => {
		if (!deployment.schedules) {
			return [];
		}
		return deployment.schedules.sort((a, b) => {
			if (!a.created) {
				return -1;
			}
			if (!b.created) {
				return 1;
			}
			return Date.parse(a.created) - Date.parse(b.created);
		});
	}, [deployment.schedules]);

	return (
		<div className="flex flex-col gap-1">
			<div className="flex items-center justify-between">
				<Typography variant="bodySmall" className="text-muted-foreground">
					Schedules
				</Typography>
				{(deploymentSchedulesSorted.length > NUM_SCHEDULES_TO_TOGGLE ||
					deployment.paused) && (
					<DeploymentScheduleToggle deployment={deployment} />
				)}
			</div>
			<div className="flex flex-col gap-2">
				{deploymentSchedulesSorted.map((schedule) => (
					<DeploymentScheduleItem
						key={schedule.id}
						disabled={deployment.paused}
						deploymentSchedule={schedule}
						onEditSchedule={onEditSchedule}
					/>
				))}
				<div>
					<Button size="sm" onClick={onAddSchedule}>
						<Icon id="Plus" className="mr-2 size-4" /> Schedule
					</Button>
				</div>
			</div>
		</div>
	);
};
