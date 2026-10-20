import { useMemo, useState } from "react";
import {
	STATE_NAMES,
	STATE_NAMES_WITHOUT_SCHEDULED,
} from "@/api/flow-runs/constants";
import { useStateOptions } from "@/api/observed-states";
import { StateNameBadge } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-name-badge";
import {
	Combobox,
	ComboboxCommandEmtpy,
	ComboboxCommandGroup,
	ComboboxCommandInput,
	ComboboxCommandItem,
	ComboboxCommandList,
	ComboboxContent,
	ComboboxTrigger,
} from "@/components/ui/combobox";

const ALL_RUN_STATES = "All run states";
const ALL_EXCEPT_SCHEDULED = "All except scheduled";

type StateMultiSelectProps = {
	selectedStates: string[];
	onStateChange: (states: string[]) => void;
	emptyMessage?: string;
};

function isAllExceptScheduled(states: string[]): boolean {
	if (states.length !== STATE_NAMES.length - 1) return false;
	return STATE_NAMES_WITHOUT_SCHEDULED.every((name) => states.includes(name));
}

export function StateMultiSelect({
	selectedStates,
	onStateChange,
	emptyMessage = "Any state",
}: StateMultiSelectProps) {
	const [search, setSearch] = useState("");
	const [open, setOpen] = useState(false);
	const {
		names: filteredStates,
		data,
		isFetching,
		isError,
	} = useStateOptions(search, selectedStates, open);

	const displayValue = useMemo(() => {
		if (selectedStates.length === 0) {
			return ALL_RUN_STATES;
		}
		if (isAllExceptScheduled(selectedStates)) {
			return ALL_EXCEPT_SCHEDULED;
		}
		return selectedStates;
	}, [selectedStates]);

	const showConvenienceOptions = useMemo(() => {
		const lowerSearch = search.toLowerCase();
		return (
			ALL_RUN_STATES.toLowerCase().includes(lowerSearch) ||
			ALL_EXCEPT_SCHEDULED.toLowerCase().includes(lowerSearch)
		);
	}, [search]);

	const handleConvenienceSelect = (option: string) => {
		if (option === ALL_RUN_STATES) {
			onStateChange([]);
		} else if (option === ALL_EXCEPT_SCHEDULED) {
			onStateChange([...STATE_NAMES_WITHOUT_SCHEDULED]);
		}
		setSearch("");
	};

	const handleStateToggle = (stateName: string) => {
		if (selectedStates.includes(stateName)) {
			onStateChange(selectedStates.filter((s) => s !== stateName));
		} else {
			onStateChange([...selectedStates, stateName]);
		}
		setSearch("");
	};

	const renderSelectedStates = () => {
		if (displayValue === ALL_RUN_STATES) {
			return <span className="text-muted-foreground">{emptyMessage}</span>;
		}
		if (displayValue === ALL_EXCEPT_SCHEDULED) {
			return <span>All except scheduled</span>;
		}
		return (
			<div className="flex flex-wrap gap-1">
				{selectedStates.map((stateName) => (
					<StateNameBadge key={stateName} name={stateName} />
				))}
			</div>
		);
	};

	return (
		<Combobox onOpenChange={setOpen}>
			<ComboboxTrigger selected={selectedStates.length > 0}>
				{renderSelectedStates()}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search states..."
				/>
				<ComboboxCommandEmtpy>No state found</ComboboxCommandEmtpy>
				<ComboboxCommandList>
					{isFetching && <p role="status">Loading states...</p>}
					{isError && <p role="status">Could not load observed states.</p>}
					{data?.length === 200 && (
						<p className="text-sm text-muted-foreground">
							Showing up to 200 observed states. Search by prefix to find more.
						</p>
					)}
					<ComboboxCommandGroup>
						{showConvenienceOptions && (
							<>
								<ComboboxCommandItem
									key={ALL_RUN_STATES}
									selected={displayValue === ALL_RUN_STATES}
									onSelect={() => handleConvenienceSelect(ALL_RUN_STATES)}
									value={ALL_RUN_STATES}
									closeOnSelect={false}
								>
									All run states
								</ComboboxCommandItem>
								<ComboboxCommandItem
									key={ALL_EXCEPT_SCHEDULED}
									selected={displayValue === ALL_EXCEPT_SCHEDULED}
									onSelect={() => handleConvenienceSelect(ALL_EXCEPT_SCHEDULED)}
									value={ALL_EXCEPT_SCHEDULED}
									closeOnSelect={false}
								>
									All except scheduled
								</ComboboxCommandItem>
							</>
						)}
						{filteredStates.map((stateName) => (
							<ComboboxCommandItem
								key={stateName}
								selected={selectedStates.includes(stateName)}
								onSelect={() => handleStateToggle(stateName)}
								value={stateName}
								closeOnSelect={false}
							>
								<StateNameBadge name={stateName} />
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}
