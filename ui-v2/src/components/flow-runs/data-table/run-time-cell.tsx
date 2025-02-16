import {
	type FlowRun,
	type FlowRunWithDeploymentAndFlow,
} from "@/api/flow-runs";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";
import { formatDate } from "@/utils/date";

type RunTimeCellProps = {
	flowRun: FlowRun | FlowRunWithDeploymentAndFlow;
};

export const RunTimeCell = ({ flowRun }: RunTimeCellProps) => {
	const { start_time, expected_start_time } = flowRun;
	let text = "No start time";
	if (start_time) {
		text = formatDate(start_time, "dateTimeNumeric");
	} else if (expected_start_time) {
		text = formatDate(expected_start_time, "dateTimeNumeric");
	}

	return (
		<Typography
			variant="bodySmall"
			fontFamily="mono"
			className="flex gap-2 items-center min-w-60"
		>
			<Icon id="Calendar" className="h-4 w-4" />
			{text}
		</Typography>
	);
};
