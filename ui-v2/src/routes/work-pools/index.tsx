import {
	buildCountWorkPoolsQuery,
	buildFilterWorkPoolsQuery,
} from "@/api/work-pools";
import { WorkPoolsEmptyState } from "@/components/work-pools/empty-state";
import { WorkPoolsPageHeader } from "@/components/work-pools/header";
import { WorkPoolsDataTable } from "@/components/work-pools/work-pools-table";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/work-pools/")({
	component: RouteComponent,
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

	const { data: workPoolCount = 0 } = useSuspenseQuery(
		buildCountWorkPoolsQuery(),
	);

	const { data: workPools = [] } = useSuspenseQuery(
		buildFilterWorkPoolsQuery({
			limit: 200,
			offset: 0,
		}),
	);

        return (
                <div className="flex flex-col gap-4">
                        <WorkPoolsPageHeader />
                        {workPoolCount < 1 ? (
                                <WorkPoolsEmptyState />
                        ) : (
                                <WorkPoolsDataTable workPools={workPools} totalCount={workPoolCount} />
                        )}
                </div>
        );
}
