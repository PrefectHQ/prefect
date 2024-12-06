import { Flex } from "@/components/ui/flex";
import { Typography } from "@/components/ui/typography";

import { ConcurrencyTabs } from "./concurrency-tabs";
import { GlobalConcurrencyView } from "./global-concurrency-view";
import { TaskRunConcurrencyView } from "./task-run-concurrenct-view";

export const ConcurrencyPage = (): JSX.Element => {
	return (
		<Flex flexDirection="column" gap={4}>
			<Typography variant="h2">Concurrency</Typography>
			<ConcurrencyTabs
				globalView={<GlobalConcurrencyView />}
				taskRunView={<TaskRunConcurrencyView />}
			/>
		</Flex>
	);
};
