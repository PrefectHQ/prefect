import { useSuspenseQuery } from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { categorizeError } from "@/api/error-utils";
import {
	buildCountWorkPoolsQuery,
	buildFilterWorkPoolsQuery,
} from "@/api/work-pools";
import { SearchInput } from "@/components/ui/input";
import { RouteErrorState } from "@/components/ui/route-error-state";
import { WorkPoolsEmptyState } from "@/components/work-pools/empty-state";
import { WorkPoolsPageHeader } from "@/components/work-pools/header";
import { WorkPoolCard } from "@/components/work-pools/work-pool-card/work-pool-card";
import { pluralize } from "@/utils";

function WorkPoolsErrorComponent({ error, reset }: ErrorComponentProps) {
	const serverError = categorizeError(error, "Failed to load work pools");

	// Only handle API errors (server-error, client-error) at route level
	// Let network errors and unknown errors bubble up to root error component
	if (
		serverError.type !== "server-error" &&
		serverError.type !== "client-error"
	) {
		throw error;
	}

	return (
		<div className="flex flex-col gap-4">
			<WorkPoolsPageHeader />
			<RouteErrorState error={serverError} onRetry={reset} />
		</div>
	);
}

export const Route = createFileRoute("/work-pools/")({
	component: RouteComponent,
	errorComponent: WorkPoolsErrorComponent,
	loader: ({ context }) => {
		void context.queryClient.ensureQueryData(buildCountWorkPoolsQuery());
		void context.queryClient.ensureQueryData(
			buildFilterWorkPoolsQuery({
				limit: 200,
				offset: 0,
			}),
		);
	},
	wrapInSuspense: true,
});

function RouteComponent() {
	const [searchTerm, setSearchTerm] = useState("");

	const { data: workPoolCount = 0 } = useSuspenseQuery(
		buildCountWorkPoolsQuery(),
	);

	const { data: workPools = [] } = useSuspenseQuery(
		buildFilterWorkPoolsQuery({
			limit: 200,
			offset: 0,
		}),
	);

	const filteredWorkPools = useMemo(() => {
		return workPools.filter((workPool) =>
			[
				workPool.name,
				workPool.description,
				workPool.type,
				JSON.stringify(workPool.base_job_template),
				workPool.id,
				workPool.default_queue_id,
				workPool.status,
			]
				.join(" ")
				.toLowerCase()
				.includes(searchTerm.toLowerCase()),
		);
	}, [workPools, searchTerm]);

	const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
		setSearchTerm(event.target.value);
	};

	return (
		<div className="flex flex-col gap-4">
			<WorkPoolsPageHeader />
			{workPoolCount < 1 ? (
				<WorkPoolsEmptyState />
			) : (
				<>
					<div className="flex items-end justify-between">
						<div className="text-sm text-muted-foreground">
							{workPoolCount} {pluralize(workPoolCount, "work pool")}
						</div>
						<div className="flex gap-2">
							<SearchInput
								placeholder="Search work pools..."
								value={searchTerm}
								onChange={handleSearchChange}
							/>
						</div>
					</div>
					<div className="flex flex-col gap-4">
						{filteredWorkPools.map((workPool) => (
							<WorkPoolCard key={workPool.id} workPool={workPool} />
						))}
					</div>
				</>
			)}
		</div>
	);
}
