import {
	buildCountWorkPoolsQuery,
	buildFilterWorkPoolsQuery,
} from "@/api/work-pools";
import { Input } from "@/components/ui/input";
import { WorkPoolsPageHeader } from "@/components/work-pools/header";
import { WorkPoolCard } from "@/components/work-pools/work-pool-card/work-pool-card";
import { pluralize } from "@/utils";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { useMemo, useState } from "react";

export const Route = createFileRoute("/work-pools/")({
	component: RouteComponent,
});

function RouteComponent() {
	const [searchTerm, setSearchTerm] = useState("");

	const { data: workPoolCount = 0 } = useQuery(buildCountWorkPoolsQuery());

	const { data: workPools = [] } = useQuery(
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
		// TODO: Should we just standardize a layout for all pages?
		<div className="flex flex-col gap-4">
			<WorkPoolsPageHeader />
			<div className="flex justify-between">
				<div className="text-sm text-muted-foreground">
					{workPoolCount} {pluralize(workPoolCount, "work pool")}
				</div>
				<div className="flex gap-2">
					<div className="relative">
						<Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
						<Input
							placeholder="Search work pools..."
							className="pl-8 w-[250px]"
							value={searchTerm}
							onChange={handleSearchChange}
						/>
					</div>
				</div>
			</div>
			<div className="flex flex-col gap-4">
				{filteredWorkPools.map((workPool) => (
					<WorkPoolCard key={workPool.id} workPool={workPool} />
				))}
			</div>
		</div>
	);
}
