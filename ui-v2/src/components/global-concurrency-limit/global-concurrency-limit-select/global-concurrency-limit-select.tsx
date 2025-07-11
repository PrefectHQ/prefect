import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useDeferredValue, useMemo, useState } from "react";
import { buildListGlobalConcurrencyLimitsQuery } from "@/api/global-concurrency-limits";
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

type GlobalConcurrencyLimitSelectProps = {
	presetOptions?: Array<PresetOption>;
	selected: string | undefined | null;
	onSelect: (name: string | undefined | null) => void;
};

export const GlobalConcurrencyLimitSelect = ({
	presetOptions = [],
	selected,
	onSelect,
}: GlobalConcurrencyLimitSelectProps) => {
	return (
		<Suspense>
			<GlobalConcurrencyLimitSelectImplementation
				presetOptions={presetOptions}
				selected={selected}
				onSelect={onSelect}
			/>
		</Suspense>
	);
};

const GlobalConcurrencyLimitSelectImplementation = ({
	presetOptions = [],
	selected,
	onSelect,
}: GlobalConcurrencyLimitSelectProps) => {
	const [search, setSearch] = useState("");
	const { data } = useSuspenseQuery(buildListGlobalConcurrencyLimitsQuery());

	const deferredSearch = useDeferredValue(search);
	const filteredData = useMemo(() => {
		return data.filter((globalConcurrencyLimit) =>
			globalConcurrencyLimit.name
				.toLowerCase()
				.includes(deferredSearch.toLowerCase()),
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
				aria-label="Select a global concurrency limit"
			>
				{
					data.find(
						(globalConcurrencyLimit) => globalConcurrencyLimit.id === selected,
					)?.name
				}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search for a global concurrency limit..."
				/>
				<ComboboxCommandEmtpy>
					No global concurrency limit found
				</ComboboxCommandEmtpy>
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
						{filteredData.map((globalConcurrencyLimit) => (
							<ComboboxCommandItem
								key={globalConcurrencyLimit.id}
								selected={selected === globalConcurrencyLimit.name}
								onSelect={(value) => {
									onSelect(value);
									setSearch("");
								}}
								value={globalConcurrencyLimit.id}
							>
								{globalConcurrencyLimit.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
