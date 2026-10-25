import { useMemo, useState } from "react";
import { useStateOptions } from "@/api/observed-states";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { SearchInput } from "@/components/ui/input";
import { FLOW_RUN_STATES_NO_SCHEDULED } from "./state-filters.constants";
import { StateNameBadge } from "./state-name-badge";

const MAX_FILTERS_DISPLAYED = 2;

type StateFilterProps = {
	defaultValue?: Set<string>;
	selectedFilters: Set<string> | undefined;
	onSelectFilter: (filters: Set<string>) => void;
};

export const StateFilter = ({
	defaultValue,
	selectedFilters = defaultValue || new Set(),
	onSelectFilter,
}: StateFilterProps) => {
	const [open, setOpen] = useState(false);
	const [search, setSearch] = useState("");
	const { names, data, isFetching, isError } = useStateOptions(
		search,
		[...selectedFilters],
		open,
	);

	const isAllButScheduled = useMemo(() => {
		const flowRunStatesNoScheduleSet = new Set<string>(
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

	const handleSelectFilter = (filter: string) => {
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
						<StateNameBadge key={filter} name={filter} />
					))}
				</div>
				{extraCount > 0 && <p className="text-sm shrink-0">+ {extraCount}</p>}
			</div>
		);
	};

	return (
		<DropdownMenu open={open} onOpenChange={setOpen}>
			<DropdownMenuTrigger asChild>
				<Button
					variant="outline"
					className="justify-between w-full bg-card dark:bg-background"
				>
					<span className="flex-1 min-w-0">{renderSelectedTags()}</span>
					<Icon id="ChevronDown" className="ml-2 size-4 shrink-0" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent className="max-h-96 overflow-x-hidden overflow-y-auto">
				<SearchInput
					debounceMs={0}
					aria-label="Search state names"
					placeholder="Search state names..."
					value={search}
					onChange={(event) => setSearch(event.target.value)}
					onKeyDown={(event) => {
						if (event.key !== "Escape") event.stopPropagation();
					}}
				/>
				{isFetching && (
					<p role="status" className="px-2 text-sm">
						Loading states...
					</p>
				)}
				{isError && (
					<p role="status" className="px-2 text-sm">
						Could not load observed states. Built-in and selected names are
						available.
					</p>
				)}
				{data?.length === 200 && (
					<p className="px-2 text-sm text-muted-foreground">
						Showing up to 200 observed states. Search by prefix to find more.
					</p>
				)}
				{!isFetching && !isError && names.length === 0 && (
					<p role="status" className="px-2 text-sm">
						No state names found.
					</p>
				)}
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
				{names.map((filterKey) => (
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
							checked={!isAllButScheduled && selectedFilters.has(filterKey)}
						/>
						<StateNameBadge name={filterKey} />
					</DropdownMenuItem>
				))}
			</DropdownMenuContent>
		</DropdownMenu>
	);
};
