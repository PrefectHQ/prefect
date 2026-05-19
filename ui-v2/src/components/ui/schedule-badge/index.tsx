import cronstrue from "cronstrue";
import { format } from "date-fns";
import humanizeDuration from "humanize-duration";
import { useRef } from "react";
import { rrulestr } from "rrule";
import type { components } from "@/api/prefect";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icons";
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
import { capitalize, cn, intervalToSeconds } from "@/utils";

type DeploymentSchedule = components["schemas"]["DeploymentSchedule"];
type CronSchedule = components["schemas"]["CronSchedule"];
type IntervalSchedule = components["schemas"]["IntervalSchedule"];
type RRuleSchedule = components["schemas"]["RRuleSchedule"];

type ScheduleBadgeProps = BadgeProps & {
	schedule: DeploymentSchedule;
};

const getScheduleStatusLabel = (active: boolean) =>
	active ? "Active" : "Paused";

const ScheduleStatusPill = ({ active }: { active: boolean }) => (
	<span
		className={cn(
			"inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium leading-none",
			active
				? "bg-state-completed-100 text-state-completed-700"
				: "bg-state-paused-100 text-state-paused-700",
		)}
	>
		<Icon id={active ? "Check" : "Pause"} className="size-3" aria-hidden="true" />
		<span>{getScheduleStatusLabel(active)}</span>
	</span>
);

const getScheduleBadgeClassName = (className?: string) =>
	cn("gap-2 justify-start", className);

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
	const badgeVariant = active ? "success" : "warning";

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger>
					<Badge
						variant={badgeVariant}
						{...props}
						className={getScheduleBadgeClassName(props.className)}
					>
						<ScheduleStatusPill active={active} />
						<span className="min-w-0 truncate">{scheduleText}</span>
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
	const scheduleText = `Every ${humanizeDuration(intervalToSeconds(schedule.interval) * 1000)}`;
	let detailedScheduleText = `${active ? "" : "(Paused)"} ${scheduleText}`;
	if (schedule.anchor_date) {
		detailedScheduleText += ` using ${format(
			new Date(schedule.anchor_date),
			"MMM do, yyyy 'at' hh:mm:ss aa",
		)} (${schedule.timezone}) as the anchor date`;
	}
	const badgeVariant = active ? "success" : "warning";

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger>
					<Badge
						variant={badgeVariant}
						{...props}
						className={getScheduleBadgeClassName(props.className)}
					>
						<ScheduleStatusPill active={active} />
						<span className="min-w-0 truncate">{scheduleText}</span>
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
	const badgeVariant = active ? "success" : "warning";

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger>
					<Badge
						variant={badgeVariant}
						{...props}
						className={getScheduleBadgeClassName(props.className)}
					>
						<ScheduleStatusPill active={active} />
						<span className="min-w-0 truncate">{capitalizedScheduleText}</span>
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
