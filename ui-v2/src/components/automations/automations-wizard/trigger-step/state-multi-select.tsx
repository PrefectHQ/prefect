import { useDeferredValue, useMemo, useState } from "react";
import {
	STATE_NAME_TO_TYPE,
	STATE_NAMES,
	STATE_NAMES_WITHOUT_SCHEDULED,
	type StateName,
} from "@/api/flow-runs/constants";
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
import { StateBadge } from "@/components/ui/state-badge";

const ALL_RUN_STATES = "All run states";
const ALL_EXCEPT_SCHEDULED = "All except scheduled";

type StateMultiSelectProps = {
	selectedStates: StateName[];
	onStateChange: (states: StateName[]) => void;
	emptyMessage?: string;
};

function isAllExceptScheduled(states: StateName[]): boolean {
	if (states.length !== STATE_NAMES.length - 1) return false;
	return !states.includes("Scheduled");
}

export function StateMultiSelect({
	selectedStates,
	onStateChange,
	emptyMessage = "Any state",
}: StateMultiSelectProps) {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const displayValue = useMemo(() => {
		if (selectedStates.length === 0) {
			return ALL_RUN_STATES;
		}
		if (isAllExceptScheduled(selectedStates)) {
			return ALL_EXCEPT_SCHEDULED;
		}
		return selectedStates;
	}, [selectedStates]);

	const filteredStates = useMemo(() => {
		const lowerSearch = deferredSearch.toLowerCase();
		return STATE_NAMES.filter((name) =>
			name.toLowerCase().includes(lowerSearch),
		);
	}, [deferredSearch]);

	const showConvenienceOptions = useMemo(() => {
		const lowerSearch = deferredSearch.toLowerCase();
		return (
			ALL_RUN_STATES.toLowerCase().includes(lowerSearch) ||
			ALL_EXCEPT_SCHEDULED.toLowerCase().includes(lowerSearch)
		);
	}, [deferredSearch]);

	const handleConvenienceSelect = (option: string) => {
		if (option === ALL_RUN_STATES) {
			onStateChange([]);
		} else if (option === ALL_EXCEPT_SCHEDULED) {
			onStateChange([...STATE_NAMES_WITHOUT_SCHEDULED]);
		}
		setSearch("");
	};

	const handleStateToggle = (stateName: StateName) => {
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
					<StateBadge
						key={stateName}
						type={STATE_NAME_TO_TYPE[stateName]}
						name={stateName}
						className="cursor-pointer"
					/>
				))}
			</div>
		);
	};

	return (
		<Combobox>
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
								<StateBadge
									type={STATE_NAME_TO_TYPE[stateName]}
									name={stateName}
								/>
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}
