import humanizeDuration from "humanize-duration";
import { useMemo } from "react";
import type { FlowRunCardData } from "@/components/flow-runs/flow-run-card";
import { Icon } from "@/components/ui/icons";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatDate } from "@/utils/date";

type FlowRunStartTimeProps = { flowRun: FlowRunCardData };
export const FlowRunStartTime = ({ flowRun }: FlowRunStartTimeProps) => {
	const { start_time, expected_start_time, estimated_start_time_delta } =
		flowRun;

	const { text, tooltipText } = useMemo(() => {
		let text: string | undefined;
		let tooltipText: string | undefined;
		if (start_time) {
			text = `${formatDate(start_time, "dateTimeNumeric")} ${getDelta(estimated_start_time_delta)}`;
			tooltipText = new Date(start_time).toString();
		} else if (expected_start_time) {
			text = `Scheduled for ${formatDate(expected_start_time, "dateTimeNumeric")} ${getDelta(estimated_start_time_delta)}`;
			tooltipText = new Date(expected_start_time).toString();
		}
		return { text, tooltipText };
	}, [estimated_start_time_delta, expected_start_time, start_time]);

	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger asChild disabled={!text}>
					<div className="text-xs font-mono flex gap-2 items-center">
						<Icon id="Calendar" className="size-4" />
						{text ?? "No start time"}
					</div>
				</TooltipTrigger>
				<TooltipContent>{tooltipText}</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
};

const getDelta = (estimated_start_time_delta: null | number) => {
	if (!estimated_start_time_delta || estimated_start_time_delta <= 60) {
		return "";
	}
	return `(${humanizeDuration(estimated_start_time_delta, { maxDecimalPoints: 0 })} late)`;
};
