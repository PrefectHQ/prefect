import type { JSX } from "react";

import { Typography } from "@/components/ui/typography";

import { ConcurrencyTabs } from "./concurrency-tabs";
import { GlobalConcurrencyView } from "./global-concurrency-view";
import { TaskRunConcurrencyView } from "./task-run-concurrency-view";

export const ConcurrencyPage = (): JSX.Element => {
	return (
		<div className="flex flex-col gap-4">
			<Typography variant="h2">Concurrency</Typography>
			<ConcurrencyTabs
				globalView={<GlobalConcurrencyView />}
				taskRunView={<TaskRunConcurrencyView />}
			/>
		</div>
	);
};
