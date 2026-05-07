import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import type { DeploymentSchedule } from "@/api/deployments";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icons";

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

	return (
		<Card className="p-3">
			<div className="flex items-center justify-between gap-2">
				<div className="flex items-center gap-2 flex-1">
					<TooltipProvider>
						<Tooltip>
							<TooltipTrigger asChild>
								<div
									className={`shrink-0 rounded-full p-1 ${
										isActive
											? "bg-green-100 dark:bg-green-900"
											: "bg-yellow-100 dark:bg-yellow-900"
									}`}
								>
									<Icon
										id={isActive ? "Check" : "Pause"}
										className={`size-4 ${
											isActive
												? "text-green-600 dark:text-green-400"
												: "text-yellow-600 dark:text-yellow-400"
										}`}
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
