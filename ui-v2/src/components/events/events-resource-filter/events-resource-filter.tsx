import { Suspense, useDeferredValue, useMemo, useState } from "react";
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
import {
	type ResourceOption,
	useResourceOptions,
} from "./use-resource-options";

export type EventsResourceFilterProps = {
	selectedResourceIds: string[];
	onResourceIdsChange: (resourceIds: string[]) => void;
};

const RESOURCE_TYPE_DISPLAY_NAMES: Record<ResourceOption["type"], string> = {
	automation: "Automation",
	block: "Block",
	deployment: "Deployment",
	flow: "Flow",
	"work-pool": "Work Pool",
	"work-queue": "Work Queue",
};

export function EventsResourceFilter(props: EventsResourceFilterProps) {
	return (
		<Suspense>
			<EventsResourceFilterImplementation {...props} />
		</Suspense>
	);
}

function EventsResourceFilterImplementation({
	selectedResourceIds,
	onResourceIdsChange,
}: EventsResourceFilterProps) {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const { resourceOptions } = useResourceOptions();

	const filteredOptions = useMemo(() => {
		if (!deferredSearch) {
			return resourceOptions;
		}
		return resourceOptions.filter((option) =>
			option.name.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [resourceOptions, deferredSearch]);

	const groupedOptions = useMemo(() => {
		const groups: Record<ResourceOption["type"], ResourceOption[]> = {
			automation: [],
			block: [],
			deployment: [],
			flow: [],
			"work-pool": [],
			"work-queue": [],
		};

		for (const option of filteredOptions) {
			groups[option.type].push(option);
		}

		return groups;
	}, [filteredOptions]);

	const handleToggleResource = (resourceId: string) => {
		const isSelected = selectedResourceIds.includes(resourceId);
		if (isSelected) {
			onResourceIdsChange(
				selectedResourceIds.filter((id) => id !== resourceId),
			);
		} else {
			onResourceIdsChange([...selectedResourceIds, resourceId]);
		}
		setSearch("");
	};

	return (
		<Combobox>
			<ComboboxTrigger
				aria-label="Filter by resource"
				selected={selectedResourceIds.length > 0}
			>
				{selectedResourceIds.length > 0
					? `${selectedResourceIds.length} resource${selectedResourceIds.length === 1 ? "" : "s"} selected`
					: "All resources"}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search resources..."
				/>
				<ComboboxCommandEmtpy>No resources found</ComboboxCommandEmtpy>
				<ComboboxCommandList>
					{(
						Object.entries(groupedOptions) as [
							ResourceOption["type"],
							ResourceOption[],
						][]
					).map(([type, options]) =>
						options.length > 0 ? (
							<ComboboxCommandGroup
								key={type}
								heading={RESOURCE_TYPE_DISPLAY_NAMES[type]}
							>
								{options.map((option) => (
									<ComboboxCommandItem
										key={option.resourceId}
										value={option.resourceId}
										selected={selectedResourceIds.includes(option.resourceId)}
										onSelect={handleToggleResource}
										closeOnSelect={false}
									>
										{option.name}
									</ComboboxCommandItem>
								))}
							</ComboboxCommandGroup>
						) : null,
					)}
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}
