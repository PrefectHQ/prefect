import { useDeferredValue, useMemo, useState } from "react";
import {
	type ResourceOption,
	useResourceOptions,
} from "@/components/events/events-resource-filter/use-resource-options";
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

export type EventResourceComboboxProps = {
	selectedResourceIds: string[];
	onToggleResource: (resourceId: string) => void;
	emptyMessage?: string;
};

const RESOURCE_TYPE_DISPLAY_NAMES: Record<ResourceOption["type"], string> = {
	automation: "Automation",
	block: "Block",
	deployment: "Deployment",
	flow: "Flow",
	"work-pool": "Work Pool",
	"work-queue": "Work Queue",
};

export function EventResourceCombobox({
	selectedResourceIds,
	onToggleResource,
	emptyMessage = "All resources",
}: EventResourceComboboxProps) {
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

	const showCustomOption = useMemo(() => {
		if (!deferredSearch.trim()) return false;
		return !resourceOptions.some(
			(opt) => opt.resourceId.toLowerCase() === deferredSearch.toLowerCase(),
		);
	}, [deferredSearch, resourceOptions]);

	const renderSelectedResources = () => {
		if (selectedResourceIds.length === 0) {
			return <span className="text-muted-foreground">{emptyMessage}</span>;
		}

		const selectedNames = selectedResourceIds.map((id) => {
			const option = resourceOptions.find((opt) => opt.resourceId === id);
			return option?.name ?? id;
		});

		const visibleNames = selectedNames.slice(0, 2);
		const overflow = selectedNames.length - visibleNames.length;

		return (
			<div className="flex min-w-0 items-center justify-start gap-1">
				<span className="truncate min-w-0 text-left">
					{visibleNames.join(", ")}
				</span>
				{overflow > 0 && (
					<span className="shrink-0 text-muted-foreground">+{overflow}</span>
				)}
			</div>
		);
	};

	const handleSelect = (resourceId: string) => {
		onToggleResource(resourceId);
		setSearch("");
	};

	return (
		<Combobox>
			<ComboboxTrigger selected={selectedResourceIds.length > 0}>
				{renderSelectedResources()}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search resources..."
				/>
				<ComboboxCommandList>
					<ComboboxCommandEmtpy>No resources found</ComboboxCommandEmtpy>
					{showCustomOption && (
						<ComboboxCommandGroup>
							<ComboboxCommandItem
								key="__custom__"
								selected={selectedResourceIds.includes(deferredSearch)}
								onSelect={() => handleSelect(deferredSearch)}
								closeOnSelect={false}
								value={deferredSearch}
							>
								Add &quot;{deferredSearch}&quot;
							</ComboboxCommandItem>
						</ComboboxCommandGroup>
					)}
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
										onSelect={handleSelect}
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
