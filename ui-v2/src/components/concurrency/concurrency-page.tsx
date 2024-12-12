import type { JSX } from "react";

import { Typography } from "@/components/ui/typography";

import { ConcurrencyTabs } from "./concurrency-tabs";
import { GlobalConcurrencyLimitsView } from "./global-concurrency-limits-view";
import { TaskRunConcurrencyLimitsView } from "./task-run-concurrency-limits-view";

export const ConcurrencyPage = (): JSX.Element => {
	return (
		<div className="flex flex-col gap-4">
			<Typography variant="h2">Concurrency</Typography>
			<ConcurrencyTabs
				globalView={<GlobalConcurrencyLimitsView />}
				taskRunView={<TaskRunConcurrencyLimitsView />}
			/>
		</div>
	);
};
