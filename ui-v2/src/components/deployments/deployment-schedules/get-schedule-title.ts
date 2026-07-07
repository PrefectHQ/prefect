import cronstrue from "cronstrue";
import humanizeDuration from "humanize-duration";
import { rrulestr } from "rrule";
import type { DeploymentSchedule } from "@/api/deployments";
import { divergesFromServerCron } from "@/components/ui/cron-input";
import { intervalToSeconds } from "@/utils";

export const getScheduleTitle = (deploymentSchedule: DeploymentSchedule) => {
	const { schedule } = deploymentSchedule;
	if ("interval" in schedule) {
		return `Every ${humanizeDuration(intervalToSeconds(schedule.interval) * 1_000)}`;
	}
	if ("cron" in schedule) {
		if (divergesFromServerCron(schedule.cron)) {
			return schedule.cron;
		}
		return cronstrue.toString(schedule.cron);
	}
	return rrulestr(schedule.rrule).toText();
};
