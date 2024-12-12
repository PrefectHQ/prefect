import type { components } from "@/api/prefect";
import { Badge } from "../badge";

export type ScheduleBadgeProps = {
	schedule: components["schemas"]["DeploymentSchedule"];
};

export const ScheduleBadge = ({ schedule }: ScheduleBadgeProps) => {
	const { schedule: innerSchedule } = schedule;
	if ("cron" in innerSchedule) {
		return <Badge>{innerSchedule.cron}</Badge>;
	}

	if ("interval" in innerSchedule) {
		return <Badge>{innerSchedule.interval}</Badge>;
	}

	if ("rrule" in innerSchedule) {
		return <Badge>{innerSchedule.rrule}</Badge>;
	}

	return <Badge>{JSON.stringify(schedule)}</Badge>;
};
