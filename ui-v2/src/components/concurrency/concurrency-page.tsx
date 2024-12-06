import { Typography } from "@/components/ui/typography";

import { ConcurrencyTabs } from "./concurrency-tabs";
import { GlobalConcurrencyView } from "./global-concurrency-view";
import { TaskRunConcurrencyView } from "./task-run-concurrenct-view";

export const ConcurrencyPage = (): JSX.Element => {
	return (
		<div className="flex flex-col gap-4">
			<Typography variant="h2">Concurrency</Typography>
			<div className="flex flex-col gap-6">
				<ConcurrencyTabs
					globalView={<GlobalConcurrencyView />}
					taskRunView={<TaskRunConcurrencyView />}
				/>
			</div>
		</div>
	);
};
