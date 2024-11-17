import { components } from "@/api/prefect";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { PlusIcon } from "lucide-react";
import { Link } from "@tanstack/react-router";
import type { OnChangeFn, PaginationState } from "@tanstack/react-table";
import { WorkPoolsDataTable } from "@/components/work-pools/data-table";
import { WorkPoolsEmptyState } from "@/components/work-pools/empty-state";

// Define a type for the WorkPool schema
type WorkPool = components["schemas"]["WorkPool"];

type WorkPoolsPageProps = {
	workPools: WorkPool[];
	totalWorkPoolsCount: number;
	filteredWorkPoolsCount: number;
	pagination: PaginationState;
	onPaginationChange: OnChangeFn<PaginationState>;
};

const WorkPoolsPage = ({
	workPools,
	totalWorkPoolsCount,
	filteredWorkPoolsCount,
	pagination,
	onPaginationChange,
}: WorkPoolsPageProps) => {
	return (
		<div className="flex flex-col gap-4 p-4">
			<div className="flex items-center gap-2">
				<Breadcrumb>
					<BreadcrumbList>
						<BreadcrumbItem className="text-xl font-semibold">
							Work Pools
						</BreadcrumbItem>
					</BreadcrumbList>
				</Breadcrumb>
				<Button size="icon" className="h-7 w-7" variant="outline" asChild>
					<Link to="/work-pools/create">
						<PlusIcon className="h-4 w-4" />
					</Link>
				</Button>
			</div>
			{totalWorkPoolsCount === 0 ? (
				<WorkPoolsEmptyState />
			) : (
				<WorkPoolsDataTable
					workPools={workPools}
					filteredWorkPoolsCount={filteredWorkPoolsCount}
					pagination={pagination}
					onPaginationChange={onPaginationChange}
				/>
			)}
		</div>
	);
};

export default WorkPoolsPage;
