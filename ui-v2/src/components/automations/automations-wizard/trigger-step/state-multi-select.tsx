import { useDeferredValue, useMemo, useState } from "react";
import { RUN_STATES, type RunStates } from "@/api/flow-runs/constants";
import type { components } from "@/api/prefect";
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

type StateType = components["schemas"]["StateType"];

type StateMultiSelectProps = {
	selectedStates: StateType[];
	onToggleState: (state: StateType) => void;
	emptyMessage?: string;
};

export function StateMultiSelect({
	selectedStates,
	onToggleState,
	emptyMessage = "Any state",
}: StateMultiSelectProps) {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const stateEntries = useMemo(() => {
		return Object.entries(RUN_STATES) as [RunStates, string][];
	}, []);

	const filteredStates = useMemo(() => {
		return stateEntries.filter(([, displayName]) =>
			displayName.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [stateEntries, deferredSearch]);

	return (
		<Combobox>
			<ComboboxTrigger selected={selectedStates.length > 0}>
				<div className="flex flex-wrap gap-1">
					{selectedStates.length > 0 ? (
						selectedStates.map((state) => (
							<StateBadge
								key={state}
								type={state}
								name={RUN_STATES[state]}
								className="cursor-pointer"
							/>
						))
					) : (
						<span className="text-muted-foreground">{emptyMessage}</span>
					)}
				</div>
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
						{filteredStates.map(([stateKey, displayName]) => (
							<ComboboxCommandItem
								key={stateKey}
								selected={selectedStates.includes(stateKey)}
								onSelect={() => {
									onToggleState(stateKey);
									setSearch("");
								}}
								value={stateKey}
								closeOnSelect={false}
							>
								<StateBadge type={stateKey} name={displayName} />
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}
