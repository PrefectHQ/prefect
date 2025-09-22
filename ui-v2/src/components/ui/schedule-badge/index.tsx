import cronstrue from "cronstrue";
import { format } from "date-fns";
import humanizeDuration from "humanize-duration";
import { useRef } from "react";
import { rrulestr } from "rrule";
import type { components } from "@/api/prefect";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
	HoverCard,
	HoverCardContent,
	HoverCardTrigger,
} from "@/components/ui/hover-card";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { useIsOverflowing } from "@/hooks/use-is-overflowing";
import { capitalize, cn } from "@/utils";

type DeploymentSchedule = components["schemas"]["DeploymentSchedule"];
type CronSchedule = components["schemas"]["CronSchedule"];
type IntervalSchedule = components["schemas"]["IntervalSchedule"];
type RRuleSchedule = components["schemas"]["RRuleSchedule"];

type ScheduleBadgeProps = BadgeProps & {
	schedule: DeploymentSchedule;
};

export const ScheduleBadge = ({ schedule, ...props }: ScheduleBadgeProps) => {
	const { schedule: innerSchedule } = schedule;
	if ("cron" in innerSchedule) {
		return (
			<CronScheduleBadge
				schedule={innerSchedule}
				active={schedule.active}
				{...props}
			/>
		);
	}

	if ("interval" in innerSchedule) {
		return (
			<IntervalScheduleBadge
				schedule={innerSchedule}
				active={schedule.active}
				{...props}
			/>
		);
	}

	if ("rrule" in innerSchedule) {
		return (
			<RRuleScheduleBadge
				schedule={innerSchedule}
				active={schedule.active}
				{...props}
			/>
		);
	}
};

const CronScheduleBadge = ({
	active,
	schedule,
	...props
}: BadgeProps & {
	active: boolean;
	schedule: CronSchedule;
}) => {
	const scheduleText = cronstrue.toString(schedule.cron);
	const detailedScheduleText = `${active ? "" : "(Paused)"} ${scheduleText} (${schedule.timezone})`;
	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger>
					<Badge
						variant="secondary"
						className={`${!active ? "opacity-50" : ""}`}
						{...props}
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
	...props
}: BadgeProps & {
	active: boolean;
	schedule: IntervalSchedule;
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
						className={`${!active ? "opacity-50" : ""}`}
						{...props}
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
	...props
}: BadgeProps & {
	active: boolean;
	schedule: RRuleSchedule;
}) => {
	const scheduleText = rrulestr(schedule.rrule).toText();
	const capitalizedScheduleText = capitalize(scheduleText);
	const detailedScheduleText = `${active ? "" : "(Paused)"} ${capitalizedScheduleText} (${schedule.timezone})`;
	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger>
					<Badge
						variant="secondary"
						className={`${!active ? "opacity-50" : ""}`}
						{...props}
					>
						<span className="truncate">{capitalizedScheduleText}</span>
					</Badge>
				</TooltipTrigger>
				<TooltipContent>{detailedScheduleText}</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};

export const ScheduleBadgeGroup = ({
	schedules,
	className,
}: {
	schedules: DeploymentSchedule[];
	className?: string;
}) => {
	const containerRef = useRef<HTMLDivElement>(null);
	const isOverflowing = useIsOverflowing(containerRef);
	if (!schedules || schedules.length === 0) return null;

	if (isOverflowing) {
		return (
			<div
				className={cn("flex flex-row gap-2 items-center no-wrap", className)}
			>
				<HoverCard>
					<HoverCardTrigger>
						<Badge variant="secondary" className="whitespace-nowrap">
							{schedules.length} schedules
						</Badge>
					</HoverCardTrigger>
					<HoverCardContent className="flex flex-col flex-wrap gap-1 w-fit">
						{schedules.map((schedule) => (
							<ScheduleBadge key={schedule.id} schedule={schedule} />
						))}
					</HoverCardContent>
				</HoverCard>
			</div>
		);
	}

	return (
		<div
			className="flex flex-row gap-2 items-center no-wrap"
			ref={containerRef}
		>
			{schedules.map((schedule) => (
				<ScheduleBadge
					key={schedule.id}
					schedule={schedule}
					className="max-w-28"
				/>
			))}
		</div>
	);
};
