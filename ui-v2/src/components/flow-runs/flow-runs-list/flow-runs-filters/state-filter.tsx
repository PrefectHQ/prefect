import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { StateBadge } from "@/components/ui/state-badge";
import { Typography } from "@/components/ui/typography";
import {
	FLOW_RUN_STATES_MAP,
	FLOW_RUN_STATES_NO_SCHEDULED,
	type FlowRunState,
} from "./state-filters.constants";

const MAX_FILTERS_DISPLAYED = 2;

type StateFilterProps = {
	defaultValue?: Set<FlowRunState>;
	selectedFilters: Set<FlowRunState> | undefined;
	onSelectFilter: (filters: Set<FlowRunState>) => void;
};

export const StateFilter = ({
	defaultValue,
	selectedFilters = defaultValue || new Set(),
	onSelectFilter,
}: StateFilterProps) => {
	const [open, setOpen] = useState(false);

	const isAllButScheduled = useMemo(() => {
		const flowRunStatesNoScheduleSet = new Set<FlowRunState>(
			FLOW_RUN_STATES_NO_SCHEDULED,
		);
		if (
			selectedFilters.has("Scheduled") ||
			flowRunStatesNoScheduleSet.size !== selectedFilters.size
		) {
			return false;
		}
		return Array.from(selectedFilters).every((filter) =>
			flowRunStatesNoScheduleSet.has(filter),
		);
	}, [selectedFilters]);

	const handleSelectAllExceptScheduled = () => {
		onSelectFilter(new Set(FLOW_RUN_STATES_NO_SCHEDULED));
	};

	const handleSelectAllRunState = () => {
		onSelectFilter(new Set());
	};

	const handleSelectFilter = (filter: FlowRunState) => {
		// if all but scheduled is already selected, create a new set with the single filter
		if (isAllButScheduled) {
			onSelectFilter(new Set([filter]));
			return;
		}
		const updatedFilters = new Set(selectedFilters);
		if (selectedFilters.has(filter)) {
			updatedFilters.delete(filter);
		} else {
			updatedFilters.add(filter);
		}
		onSelectFilter(updatedFilters);
	};

	const renderSelectedTags = () => {
		if (selectedFilters.size === 0) {
			return "All run states";
		}
		if (isAllButScheduled) {
			return "All except scheduled";
		}

		const selected = Array.from(selectedFilters);
		const visible = selected.slice(0, MAX_FILTERS_DISPLAYED);
		const extraCount = selected.length - MAX_FILTERS_DISPLAYED;

		return (
			<div className="flex flex-1 min-w-0 items-center gap-2">
				<div className="flex flex-1 min-w-0 items-center gap-2 overflow-hidden">
					{visible.map((filter) => (
						<StateBadge
							key={filter}
							name={filter}
							type={FLOW_RUN_STATES_MAP[filter]}
						/>
					))}
				</div>
				{extraCount > 0 && (
					<Typography variant="bodySmall" className="shrink-0">
						+ {extraCount}
					</Typography>
				)}
			</div>
		);
	};

	return (
		<DropdownMenu open={open} onOpenChange={setOpen}>
			<DropdownMenuTrigger asChild>
				<Button variant="outline" className="justify-between w-full">
					<span className="flex-1 min-w-0">{renderSelectedTags()}</span>
					<Icon id="ChevronDown" className="ml-2 size-4 shrink-0" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent className="max-h-96 overflow-x-hidden overflow-y-auto">
				<DropdownMenuItem
					onSelect={(e) => {
						e.preventDefault();
						handleSelectAllExceptScheduled();
					}}
				>
					<Checkbox checked={isAllButScheduled} className="mr-2" />
					All except scheduled
				</DropdownMenuItem>
				<DropdownMenuItem
					onSelect={(e) => {
						e.preventDefault();
						handleSelectAllRunState();
					}}
				>
					<Checkbox checked={selectedFilters.size === 0} className="mr-2" />
					All run states
				</DropdownMenuItem>
				{Object.keys(FLOW_RUN_STATES_MAP).map((filterKey) => (
					<DropdownMenuItem
						aria-label={filterKey}
						key={filterKey}
						onSelect={(e) => {
							e.preventDefault();
							handleSelectFilter(filterKey as FlowRunState);
						}}
					>
						<Checkbox
							aria-label={filterKey}
							className="mr-2"
							checked={
								!isAllButScheduled &&
								selectedFilters.has(filterKey as FlowRunState)
							}
						/>
						<StateBadge
							name={filterKey}
							type={FLOW_RUN_STATES_MAP[filterKey as FlowRunState]}
						/>
					</DropdownMenuItem>
				))}
			</DropdownMenuContent>
		</DropdownMenu>
	);
};
