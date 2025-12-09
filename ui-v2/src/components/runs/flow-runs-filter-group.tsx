import { X } from "lucide-react";
import type { Deployment } from "@/api/deployments";
import type { Flow } from "@/api/flows";
import type { WorkPool } from "@/api/work-pools";
import { Button } from "@/components/ui/button";
import { RichDateRangeSelector } from "@/components/ui/date-range-select";
import { SearchInput } from "@/components/ui/input";
import { DeploymentCombobox } from "./filters/deployment-combobox";
import { FlowCombobox } from "./filters/flow-combobox";
import { StateFilter } from "./filters/state-filter";
import { TagsInput } from "./filters/tags-input";
import { WorkPoolCombobox } from "./filters/work-pool-combobox";
import type { FlowRunsFilters } from "./flow-runs-page";

type FlowRunsFilterGroupProps = {
	flows: Flow[];
	deployments: Deployment[];
	workPools: WorkPool[];
	filters: FlowRunsFilters;
};

export const FlowRunsFilterGroup = ({
	flows,
	deployments,
	workPools,
	filters,
}: FlowRunsFilterGroupProps) => {
	return (
		<div className="flex flex-col gap-4">
			<div className="flex items-center gap-2">
				<RichDateRangeSelector
					value={filters.range}
					onValueChange={filters.onDateRangeChange}
					placeholder="Select date range"
				/>
			</div>
			<div className="flex flex-wrap items-center gap-2">
				<div className="min-w-56">
					<SearchInput
						aria-label="Search by run name"
						placeholder="Search by run name"
						value={filters.search}
						onChange={(e) => filters.onSearchChange(e.target.value)}
					/>
				</div>
				<div className="min-w-48">
					<StateFilter
						selectedStates={filters.state}
						onSelectStates={filters.onStateChange}
					/>
				</div>
				<div className="min-w-48">
					<FlowCombobox
						flows={flows}
						selectedFlowIds={filters.flow}
						onSelectFlows={filters.onFlowChange}
					/>
				</div>
				<div className="min-w-48">
					<DeploymentCombobox
						deployments={deployments}
						selectedDeploymentIds={filters.deployment}
						onSelectDeployments={filters.onDeploymentChange}
					/>
				</div>
				<div className="min-w-48">
					<WorkPoolCombobox
						workPools={workPools}
						selectedWorkPoolNames={filters.workPool}
						onSelectWorkPools={filters.onWorkPoolChange}
					/>
				</div>
				<div className="min-w-48">
					<TagsInput
						selectedTags={filters.tag}
						onSelectTags={filters.onTagChange}
					/>
				</div>
				{filters.hasActiveFilters && (
					<Button
						variant="ghost"
						size="sm"
						onClick={filters.onClearFilters}
						className="text-muted-foreground"
					>
						<X className="mr-1 size-4" />
						Clear filters
					</Button>
				)}
			</div>
		</div>
	);
};
