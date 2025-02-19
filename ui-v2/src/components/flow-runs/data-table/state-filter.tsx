import { components } from "@/api/prefect";
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
import { useMemo, useState } from "react";

const FLOW_RUN_STATES = [
	"Scheduled",
	"Late",
	"Resuming",
	"AwaitingRetry",
	"AwaitingConcurrencySlot",
	"Pending",
	"Paused",
	"Suspended",
	"Running",
	"Retrying",
	"Completed",
	"Cached",
	"Cancelled",
	"Cancelling",
	"Crashed",
	"Failed",
	"TimedOut",
] as const;
export type FlowRunState = (typeof FLOW_RUN_STATES)[number];
const FLOW_RUN_STATES_NO_SCHEDULED = FLOW_RUN_STATES.filter(
	(flowStateFilter) => flowStateFilter !== "Scheduled",
);
const FLOW_RUN_STATES_MAP = {
	Scheduled: "SCHEDULED",
	Late: "SCHEDULED",
	Resuming: "SCHEDULED",
	AwaitingRetry: "SCHEDULED",
	AwaitingConcurrencySlot: "SCHEDULED",
	Pending: "PENDING",
	Paused: "PAUSED",
	Suspended: "PAUSED",
	Running: "RUNNING",
	Retrying: "RUNNING",
	Completed: "COMPLETED",
	Cached: "COMPLETED",
	Cancelled: "CANCELLED",
	Cancelling: "CANCELLING",
	Crashed: "CRASHED",
	Failed: "FAILED",
	TimedOut: "FAILED",
} satisfies Record<FlowRunState, components["schemas"]["StateType"]>;

const MAX_FILTERS_DISPLAYED = 4;

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

		return (
			<div className="flex gap-2">
				{Array.from(selectedFilters)
					.slice(0, MAX_FILTERS_DISPLAYED)
					.map((filter) => (
						<StateBadge
							key={filter}
							name={filter}
							type={FLOW_RUN_STATES_MAP[filter]}
						/>
					))}
				{selectedFilters.size > MAX_FILTERS_DISPLAYED && (
					<Typography variant="bodySmall">
						+ {selectedFilters.size - MAX_FILTERS_DISPLAYED}
					</Typography>
				)}
			</div>
		);
	};

	return (
		<DropdownMenu open={open} onOpenChange={setOpen}>
			<DropdownMenuTrigger asChild>
				<Button variant="outline" className="justify-between w-full">
					<span>{renderSelectedTags()}</span>
					<Icon id="ChevronDown" className="ml-2 h-4 w-4 flex-shrink-0" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent>
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
