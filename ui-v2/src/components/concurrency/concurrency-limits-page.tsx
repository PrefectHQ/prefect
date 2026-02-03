import { GlobalConcurrencyLimitsView } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-view";
import { TaskRunConcurrencyLimitsView } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-view";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";

import { ConcurrencyLimitsTabs } from "./concurrency-limits-tabs";

export const ConcurrencyLimitsPage = () => {
	return (
		<div className="flex flex-col gap-4">
			<ConcurrencyLimitTitle />
			<ConcurrencyLimitsTabs
				globalView={<GlobalConcurrencyLimitsView />}
				taskRunView={<TaskRunConcurrencyLimitsView />}
			/>
		</div>
	);
};

const ConcurrencyLimitTitle = () => (
	<div className="flex items-center gap-2">
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem className="text-xl font-semibold">
					Concurrency
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	</div>
);
