import type { PaginationState } from "@tanstack/react-table";
import { GlobalConcurrencyLimitsView } from "@/components/concurrency/global-concurrency-limits/global-concurrency-limits-view";
import { TaskRunConcurrencyLimitsView } from "@/components/concurrency/task-run-concurrency-limits/task-run-concurrency-limits-view";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";

import { ConcurrencyLimitsTabs } from "./concurrency-limits-tabs";

type ConcurrencyLimitsPageProps = {
	search: string | undefined;
	onSearchChange: (value: string) => void;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
};

export const ConcurrencyLimitsPage = ({
	search,
	onSearchChange,
	pagination,
	onPaginationChange,
}: ConcurrencyLimitsPageProps) => {
	return (
		<div className="flex flex-col gap-4">
			<ConcurrencyLimitTitle />
			<ConcurrencyLimitsTabs
				globalView={
					<GlobalConcurrencyLimitsView
						search={search}
						onSearchChange={onSearchChange}
						pagination={pagination}
						onPaginationChange={onPaginationChange}
					/>
				}
				taskRunView={
					<TaskRunConcurrencyLimitsView
						search={search}
						onSearchChange={onSearchChange}
						pagination={pagination}
						onPaginationChange={onPaginationChange}
					/>
				}
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
