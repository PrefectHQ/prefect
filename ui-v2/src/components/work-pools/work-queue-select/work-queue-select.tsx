import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useDeferredValue, useMemo, useState } from "react";
import { buildFilterWorkPoolWorkQueuesQuery } from "@/api/work-queues";
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

type WorkQueueSelectProps = {
	presetOptions?: Array<PresetOption>;
	selected: string | undefined | null;
	onSelect: (name: string | undefined | null) => void;
	workPoolName: string;
};

export const WorkQueueSelect = ({
	presetOptions = [],
	selected,
	onSelect,
	workPoolName,
}: WorkQueueSelectProps) => {
	return (
		<Suspense>
			<WorkQueueSelecImplementation
				presetOptions={presetOptions}
				selected={selected}
				onSelect={onSelect}
				workPoolName={workPoolName}
			/>
		</Suspense>
	);
};

const WorkQueueSelecImplementation = ({
	presetOptions = [],
	selected,
	onSelect,
	workPoolName,
}: WorkQueueSelectProps) => {
	const [search, setSearch] = useState("");
	const { data } = useSuspenseQuery(
		buildFilterWorkPoolWorkQueuesQuery({ work_pool_name: workPoolName }),
	);

	// nb: because work queues API does not have filtering _like by name, do client-side filtering
	const deferredSearch = useDeferredValue(search);
	const filteredData = useMemo(() => {
		return data.filter((workQueue) =>
			workQueue.name.toLowerCase().includes(deferredSearch.toLowerCase()),
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
				aria-label="Select a work queue"
			>
				{selected}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search for a work queue..."
				/>
				<ComboboxCommandEmtpy>No work queue found</ComboboxCommandEmtpy>
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
						{filteredData.map((workQueue) => (
							<ComboboxCommandItem
								key={workQueue.id}
								selected={selected === workQueue.name}
								onSelect={(value) => {
									onSelect(value);
									setSearch("");
								}}
								value={workQueue.name}
							>
								{workQueue.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
