import type { DeploymentSchedule } from "@/api/deployments";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icons";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";

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
	const isActive = deploymentSchedule.active && !disabled;
	const statusContainerClassName = isActive
		? "bg-state-completed-100 text-state-completed-700"
		: "bg-state-paused-100 text-state-paused-700";
	const statusIconClassName = isActive
		? "text-state-completed-600"
		: "text-state-paused-600";

	return (
		<Card className="p-3">
			<div className="flex items-center justify-between gap-2">
				<div className="flex items-center gap-2 flex-1">
					<TooltipProvider>
						<Tooltip>
							<TooltipTrigger asChild>
								<div className={`shrink-0 rounded-full p-1 ${statusContainerClassName}`}>
									<Icon
										id={isActive ? "Check" : "Pause"}
										className={`size-4 ${statusIconClassName}`}
									/>
								</div>
							</TooltipTrigger>
							<TooltipContent>
								{isActive ? "Schedule is active" : "Schedule is paused"}
							</TooltipContent>
						</Tooltip>
					</TooltipProvider>
					<p className="text-base">{getScheduleTitle(deploymentSchedule)}</p>
				</div>
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
