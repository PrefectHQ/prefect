import cronstrue from "cronstrue";
import humanizeDuration from "humanize-duration";
import { rrulestr } from "rrule";
import type { DeploymentSchedule } from "@/api/deployments";

export const getScheduleTitle = (deploymentSchedule: DeploymentSchedule) => {
	const { schedule } = deploymentSchedule;
	if ("interval" in schedule) {
		return `Every ${humanizeDuration(schedule.interval * 1_000)}`;
	}
	if ("cron" in schedule) {
		return cronstrue.toString(schedule.cron);
	}
	return rrulestr(schedule.rrule).toText();
};
