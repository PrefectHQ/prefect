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

const FLOW_RUN_STATES = [
	"Completed",
	"Running",
	"Scheduled",
	"Pending",
	"Failed",
	"Cancelled",
	"Cancelling",
	"Crashed",
	"Paused",
] as const;

type FlowRunState = (typeof FLOW_RUN_STATES)[number];

const FLOW_RUN_STATES_NO_SCHEDULED = FLOW_RUN_STATES.filter(
	(state) => state !== "Scheduled",
);

const FLOW_RUN_STATES_MAP: Record<FlowRunState, string> = {
	Completed: "COMPLETED",
	Running: "RUNNING",
	Scheduled: "SCHEDULED",
	Pending: "PENDING",
	Failed: "FAILED",
	Cancelled: "CANCELLED",
	Cancelling: "CANCELLING",
	Crashed: "CRASHED",
	Paused: "PAUSED",
};

const MAX_FILTERS_DISPLAYED = 4;

type StateFilterProps = {
	selectedStates: string[];
	onSelectStates: (states: string[]) => void;
};

export const StateFilter = ({
	selectedStates,
	onSelectStates,
}: StateFilterProps) => {
	const [open, setOpen] = useState(false);

	const selectedSet = useMemo(() => new Set(selectedStates), [selectedStates]);

	const isAllButScheduled = useMemo(() => {
		const flowRunStatesNoScheduleSet = new Set<string>(
			FLOW_RUN_STATES_NO_SCHEDULED,
		);
		if (
			selectedSet.has("Scheduled") ||
			flowRunStatesNoScheduleSet.size !== selectedSet.size
		) {
			return false;
		}
		return Array.from(selectedSet).every((filter) =>
			flowRunStatesNoScheduleSet.has(filter),
		);
	}, [selectedSet]);

	const handleSelectAllExceptScheduled = () => {
		onSelectStates([...FLOW_RUN_STATES_NO_SCHEDULED]);
	};

	const handleSelectAllRunState = () => {
		onSelectStates([]);
	};

	const handleSelectFilter = (filter: FlowRunState) => {
		if (isAllButScheduled) {
			onSelectStates([filter]);
			return;
		}
		const updatedFilters = new Set(selectedSet);
		if (selectedSet.has(filter)) {
			updatedFilters.delete(filter);
		} else {
			updatedFilters.add(filter);
		}
		onSelectStates(Array.from(updatedFilters));
	};

	const renderSelectedTags = () => {
		if (selectedSet.size === 0) {
			return "All run states";
		}
		if (isAllButScheduled) {
			return "All except scheduled";
		}

		return (
			<div className="flex gap-2">
				{Array.from(selectedSet)
					.slice(0, MAX_FILTERS_DISPLAYED)
					.map((filter) => (
						<StateBadge
							key={filter}
							name={filter}
							type={FLOW_RUN_STATES_MAP[filter as FlowRunState]}
						/>
					))}
				{selectedSet.size > MAX_FILTERS_DISPLAYED && (
					<Typography variant="bodySmall">
						+ {selectedSet.size - MAX_FILTERS_DISPLAYED}
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
					<Checkbox checked={selectedSet.size === 0} className="mr-2" />
					All run states
				</DropdownMenuItem>
				{FLOW_RUN_STATES.map((filterKey) => (
					<DropdownMenuItem
						aria-label={filterKey}
						key={filterKey}
						onSelect={(e) => {
							e.preventDefault();
							handleSelectFilter(filterKey);
						}}
					>
						<Checkbox
							aria-label={filterKey}
							className="mr-2"
							checked={!isAllButScheduled && selectedSet.has(filterKey)}
						/>
						<StateBadge
							name={filterKey}
							type={FLOW_RUN_STATES_MAP[filterKey]}
						/>
					</DropdownMenuItem>
				))}
			</DropdownMenuContent>
		</DropdownMenu>
	);
};
