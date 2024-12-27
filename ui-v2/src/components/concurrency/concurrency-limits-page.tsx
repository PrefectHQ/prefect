import { Typography } from "@/components/ui/typography";

import { GlobalConcurrencyLimitsView } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-view";
import { TaskRunConcurrencyLimitsView } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-view";
import { ConcurrencyLimitsTabs } from "./concurrency-limits-tabs";

export const ConcurrencyLimitsPage = () => {
	return (
		<div className="flex flex-col gap-4">
			<Typography variant="h2">Concurrency</Typography>
			<ConcurrencyLimitsTabs
				globalView={<GlobalConcurrencyLimitsView />}
				taskRunView={<TaskRunConcurrencyLimitsView />}
			/>
		</div>
	);
};
