import { useState } from "react";

import { Typography } from "@/components//ui/typography";

import { TAB_OPTIONS, TabOptions } from "./concurrency-constants";
import { ConcurrencyTabs } from "./concurrency-tabs";
import { GlobalConcurrencyView } from "./global-concurrency-view";
import { TaskRunConcurrencyView } from "./task-run-concurrenct-view";

export const ConcurrencyPage = (): JSX.Element => {
	// TODO: Use URL query instead
	const [tab, setTab] = useState<TabOptions>(TAB_OPTIONS.Global);

	return (
		<div className="flex flex-col gap-4">
			<Typography variant="h2">Concurrency</Typography>
			<div className="flex flex-col gap-6">
				<ConcurrencyTabs
					value={tab}
					onValueChange={setTab}
					globalView={<GlobalConcurrencyView />}
					taskRunView={<TaskRunConcurrencyView />}
				/>
			</div>
		</div>
	);
};
