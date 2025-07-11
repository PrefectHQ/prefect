import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useDeferredValue, useMemo, useState } from "react";
import { buildFilterWorkPoolsQuery } from "@/api/work-pools";
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

type PresetOption = {
	label: string;
	value: string | null | undefined;
};

type WorkPoolSelectProps = {
	presetOptions?: Array<PresetOption>;
	selected: string | undefined | null;
	onSelect: (name: string | undefined | null) => void;
};

export const WorkPoolSelect = ({
	presetOptions = [],
	selected,
	onSelect,
}: WorkPoolSelectProps) => {
	return (
		<Suspense>
			<WorkPoolSelectImplementation
				presetOptions={presetOptions}
				selected={selected}
				onSelect={onSelect}
			/>
		</Suspense>
	);
};

const WorkPoolSelectImplementation = ({
	presetOptions = [],
	selected,
	onSelect,
}: WorkPoolSelectProps) => {
	const [search, setSearch] = useState("");
	const { data } = useSuspenseQuery(buildFilterWorkPoolsQuery());

	// nb: because work pools API does not have filtering _like by name, do client-side filtering
	const deferredSearch = useDeferredValue(search);
	const filteredData = useMemo(() => {
		return data.filter((workPool) =>
			workPool.name.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [data, deferredSearch]);

	const filteredPresetOptions = useMemo(() => {
		return presetOptions.filter((option) =>
			option.label.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [deferredSearch, presetOptions]);

	return (
		<Combobox>
			<ComboboxTrigger
				selected={Boolean(selected)}
				aria-label="Select a work pool"
			>
				{selected}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search for a work pool..."
				/>
				<ComboboxCommandEmtpy>No work pool found</ComboboxCommandEmtpy>
				<ComboboxCommandList>
					<ComboboxCommandGroup>
						{filteredPresetOptions.map((option) => (
							<ComboboxCommandItem
								key={option.label}
								selected={selected === option.value}
								onSelect={() => {
									onSelect(option.value);
									setSearch("");
								}}
								//nb: Stringifies label so that UX has a hoverable state
								value={String(option.label)}
							>
								{option.label}
							</ComboboxCommandItem>
						))}
						{filteredData.map((workPool) => (
							<ComboboxCommandItem
								key={workPool.id}
								selected={selected === workPool.name}
								onSelect={(value) => {
									onSelect(value);
									setSearch("");
								}}
								value={workPool.name}
							>
								{workPool.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
