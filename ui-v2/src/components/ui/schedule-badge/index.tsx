import type { components } from "@/api/prefect";
import { Badge } from "@/components/ui/badge";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import cronstrue from "cronstrue";
import { format } from "date-fns";
import humanizeDuration from "humanize-duration";
import { rrulestr } from "rrule";

export type ScheduleBadgeProps = {
	schedule: components["schemas"]["DeploymentSchedule"];
};

export const ScheduleBadge = ({ schedule }: ScheduleBadgeProps) => {
	const { schedule: innerSchedule } = schedule;
	if ("cron" in innerSchedule) {
		return (
			<CronScheduleBadge schedule={innerSchedule} active={schedule.active} />
		);
	}

	if ("interval" in innerSchedule) {
		return (
			<IntervalScheduleBadge
				schedule={innerSchedule}
				active={schedule.active}
			/>
		);
	}

	if ("rrule" in innerSchedule) {
		return (
			<RRuleScheduleBadge schedule={innerSchedule} active={schedule.active} />
		);
	}
};

const CronScheduleBadge = ({
	active,
	schedule,
}: {
	active: boolean;
	schedule: components["schemas"]["CronSchedule"];
}) => {
	const scheduleText = cronstrue.toString(schedule.cron);
	const detailedScheduleText = `${active ? "" : "(Paused)"} ${scheduleText} (${schedule.timezone})`;
	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger>
					<Badge
						variant="secondary"
						className={`max-w-48 ${!active ? "opacity-50" : ""}`}
					>
						<span className="truncate">{scheduleText}</span>
					</Badge>
				</TooltipTrigger>
				<TooltipContent>{detailedScheduleText}</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};

const IntervalScheduleBadge = ({
	active,
	schedule,
}: {
	active: boolean;
	schedule: components["schemas"]["IntervalSchedule"];
}) => {
	const scheduleText = `Every ${humanizeDuration(schedule.interval * 1000)}`;
	let detailedScheduleText = `${active ? "" : "(Paused)"} ${scheduleText}`;
	if (schedule.anchor_date) {
		detailedScheduleText += ` using ${format(
			new Date(schedule.anchor_date),
			"MMM do, yyyy 'at' hh:mm:ss aa",
		)} (${schedule.timezone}) as the anchor date`;
	}
	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger>
					<Badge
						variant="secondary"
						className={`max-w-48 ${!active ? "opacity-50" : ""}`}
					>
						<span className="truncate">{scheduleText}</span>
					</Badge>
				</TooltipTrigger>
				<TooltipContent>{detailedScheduleText}</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};

const RRuleScheduleBadge = ({
	active,
	schedule,
}: {
	active: boolean;
	schedule: components["schemas"]["RRuleSchedule"];
}) => {
	const scheduleText = rrulestr(schedule.rrule).toText();
	const capitalizedScheduleText =
		scheduleText.charAt(0).toUpperCase() + scheduleText.slice(1);
	const detailedScheduleText = `${active ? "" : "(Paused)"} ${scheduleText} (${schedule.timezone})`;
	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger>
					<Badge
						variant="secondary"
						className={`max-w-48 ${!active ? "opacity-50" : ""}`}
					>
						<span className="truncate">{capitalizedScheduleText}</span>
					</Badge>
				</TooltipTrigger>
				<TooltipContent>{detailedScheduleText}</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};
