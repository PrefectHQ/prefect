import { useDeferredValue, useMemo, useState } from "react";
import { useResourceOptions } from "@/components/events/events-resource-filter/use-resource-options";
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

type ResourceGroup = {
	label: string;
	options: Array<{ label: string; value: string }>;
};

export function EventResourceCombobox({
	selectedResourceIds,
	onToggleResource,
	emptyMessage = "All resources",
}: EventResourceComboboxProps) {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	// Use existing hook that fetches all resource types
	const { resourceOptions } = useResourceOptions();

	// Group resources by type
	const groupedResources = useMemo(() => {
		const groups: ResourceGroup[] = [
			{ label: "Automations", options: [] },
			{ label: "Blocks", options: [] },
			{ label: "Deployments", options: [] },
			{ label: "Flows", options: [] },
			{ label: "Work Pools", options: [] },
			{ label: "Work Queues", options: [] },
		];

		for (const resource of resourceOptions) {
			const option = {
				label: resource.name,
				value: resource.resourceId,
			};

			switch (resource.type) {
				case "automation":
					groups[0].options.push(option);
					break;
				case "block":
					groups[1].options.push(option);
					break;
				case "deployment":
					groups[2].options.push(option);
					break;
				case "flow":
					groups[3].options.push(option);
					break;
				case "work-pool":
					groups[4].options.push(option);
					break;
				case "work-queue":
					groups[5].options.push(option);
					break;
			}
		}

		return groups
			.map((group) => ({
				...group,
				options: group.options.sort((a, b) => a.label.localeCompare(b.label)),
			}))
			.filter((group) => group.options.length > 0);
	}, [resourceOptions]);

	// Filter based on search
	const filteredGroups = useMemo(() => {
		if (!deferredSearch) return groupedResources;
		const lower = deferredSearch.toLowerCase();
		return groupedResources
			.map((group) => ({
				...group,
				options: group.options.filter(
					(opt) =>
						opt.label.toLowerCase().includes(lower) ||
						opt.value.toLowerCase().includes(lower),
				),
			}))
			.filter((group) => group.options.length > 0);
	}, [groupedResources, deferredSearch]);

	// Check if search term could be a custom resource ID (must contain ".")
	const showCustomOption = useMemo(() => {
		if (!deferredSearch.trim()) return false;
		if (!deferredSearch.includes(".")) return false;
		const lower = deferredSearch.toLowerCase();
		return !resourceOptions.some(
			(opt) => opt.resourceId.toLowerCase() === lower,
		);
	}, [deferredSearch, resourceOptions]);

	const renderSelectedResources = () => {
		if (selectedResourceIds.length === 0) {
			return <span className="text-muted-foreground">{emptyMessage}</span>;
		}
		const selectedNames = selectedResourceIds.map((id) => {
			const resource = resourceOptions.find((r) => r.resourceId === id);
			return resource?.name ?? id;
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

	const handleSelect = (value: string) => {
		onToggleResource(value);
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
					{filteredGroups.map((group) => (
						<ComboboxCommandGroup key={group.label} heading={group.label}>
							{group.options.map((option) => (
								<ComboboxCommandItem
									key={option.value}
									selected={selectedResourceIds.includes(option.value)}
									onSelect={() => handleSelect(option.value)}
									closeOnSelect={false}
									value={option.value}
								>
									{option.label}
								</ComboboxCommandItem>
							))}
						</ComboboxCommandGroup>
					))}
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}
