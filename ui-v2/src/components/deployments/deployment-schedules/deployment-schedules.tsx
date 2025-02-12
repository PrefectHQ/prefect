import { Deployment } from "@/api/deployments";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { useMemo } from "react";
import { DeploymentScheduleItem } from "./deployment-schedule-item";

type DeploymentSchedulesProps = {
	deployment: Deployment;
};

export const DeploymentSchedules = ({
	deployment,
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
			<div className="text-sm text-muted-foreground">Schedules</div>
			<div className="flex flex-col gap-2">
				{deploymentSchedulesSorted.map((schedule) => (
					<DeploymentScheduleItem
						key={schedule.id}
						deploymentSchedule={schedule}
					/>
				))}
				<div>
					<Button size="sm">
						<Icon id="Plus" className="mr-2 h-4 w-4" /> Schedule
					</Button>
				</div>
			</div>
		</div>
	);
};
