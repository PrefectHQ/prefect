import type { components } from "@/api/prefect";
import { Typography } from "@/components/ui/typography";

type Props = {
	data: Array<{
		taskRun: components["schemas"]["TaskRun"];
		flowRun?: components["schemas"]["FlowRun"];
		flow?: components["schemas"]["Flow"];
	}>;
};

export const TaskRunConcurrencyLimitActiveTaskRuns = ({ data }: Props) => {
	return (
		<div>
			<Typography>TODO: Active Task Runs</Typography>
			{JSON.stringify(data)}
		</div>
	);
};
