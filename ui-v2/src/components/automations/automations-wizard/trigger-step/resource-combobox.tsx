import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";
import { buildListAutomationsQuery } from "@/api/automations";
import { buildListFilterBlockDocumentsQuery } from "@/api/block-documents";
import { buildFilterDeploymentsQuery } from "@/api/deployments";
import { buildListFlowsQuery } from "@/api/flows";
import { buildFilterWorkPoolsQuery } from "@/api/work-pools";
import { buildFilterWorkQueuesQuery } from "@/api/work-queues";
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

const MAX_VISIBLE_RESOURCES = 2;

type ResourceOption = {
	label: string;
	value: string;
	type: string;
};

type ResourceGroup = {
	label: string;
	options: ResourceOption[];
};

type ResourceComboboxProps = {
	selectedResources: string[];
	onResourcesChange: (resources: string[]) => void;
	emptyMessage?: string;
};

export function ResourceCombobox({
	selectedResources,
	onResourcesChange,
	emptyMessage = "All resources",
}: ResourceComboboxProps) {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const { data: automations = [] } = useQuery(buildListAutomationsQuery());
	const { data: blocks = [] } = useQuery(buildListFilterBlockDocumentsQuery());
	const { data: deployments = [] } = useQuery(buildFilterDeploymentsQuery());
	const { data: flows = [] } = useQuery(buildListFlowsQuery());
	const { data: workPools = [] } = useQuery(buildFilterWorkPoolsQuery());
	const { data: workQueues = [] } = useQuery(buildFilterWorkQueuesQuery());

	const resourceGroups = useMemo<ResourceGroup[]>(() => {
		return [
			{
				label: "Automations",
				options: automations.map((automation) => ({
					label: automation.name,
					value: `prefect.automation.${automation.id}`,
					type: "automation",
				})),
			},
			{
				label: "Blocks",
				options: blocks.map((block) => ({
					label: block.name ?? block.id,
					value: `prefect.block-document.${block.id}`,
					type: "block-document",
				})),
			},
			{
				label: "Deployments",
				options: deployments.map((deployment) => ({
					label: deployment.name,
					value: `prefect.deployment.${deployment.id}`,
					type: "deployment",
				})),
			},
			{
				label: "Flows",
				options: flows.map((flow) => ({
					label: flow.name,
					value: `prefect.flow.${flow.id}`,
					type: "flow",
				})),
			},
			{
				label: "Work Pools",
				options: workPools.map((workPool) => ({
					label: workPool.name,
					value: `prefect.work-pool.${workPool.id}`,
					type: "work-pool",
				})),
			},
			{
				label: "Work Queues",
				options: workQueues.map((workQueue) => ({
					label: workQueue.name,
					value: `prefect.work-queue.${workQueue.id}`,
					type: "work-queue",
				})),
			},
		];
	}, [automations, blocks, deployments, flows, workPools, workQueues]);

	const filteredGroups = useMemo(() => {
		const lowerSearch = deferredSearch.toLowerCase();
		return resourceGroups
			.map((group) => ({
				...group,
				options: group.options.filter(
					(option) =>
						option.label.toLowerCase().includes(lowerSearch) ||
						option.value.toLowerCase().includes(lowerSearch),
				),
			}))
			.filter((group) => group.options.length > 0);
	}, [resourceGroups, deferredSearch]);

	const allOptions = useMemo(() => {
		return resourceGroups.flatMap((group) => group.options);
	}, [resourceGroups]);

	const handleResourceToggle = (resourceValue: string) => {
		if (selectedResources.includes(resourceValue)) {
			onResourcesChange(selectedResources.filter((r) => r !== resourceValue));
		} else {
			onResourcesChange([...selectedResources, resourceValue]);
		}
		setSearch("");
	};

	const handleAddCustomResource = () => {
		if (search.trim() && !selectedResources.includes(search.trim())) {
			onResourcesChange([...selectedResources, search.trim()]);
			setSearch("");
		}
	};

	const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.key === "Enter" && search.trim()) {
			e.preventDefault();
			handleAddCustomResource();
		}
	};

	const getResourceLabel = (resourceValue: string): string => {
		const option = allOptions.find((opt) => opt.value === resourceValue);
		return option?.label ?? resourceValue;
	};

	const renderSelectedResources = () => {
		if (selectedResources.length === 0) {
			return <span className="text-muted-foreground">{emptyMessage}</span>;
		}

		const visibleResources = selectedResources.slice(0, MAX_VISIBLE_RESOURCES);
		const overflow = selectedResources.length - visibleResources.length;

		return (
			<div className="flex min-w-0 items-center justify-start gap-1">
				<span className="truncate min-w-0 text-left">
					{visibleResources.map((r) => getResourceLabel(r)).join(", ")}
				</span>
				{overflow > 0 && (
					<span className="shrink-0 text-muted-foreground">+{overflow}</span>
				)}
			</div>
		);
	};

	const showAddCustomOption =
		search.trim() &&
		!allOptions.some(
			(opt) => opt.value.toLowerCase() === search.trim().toLowerCase(),
		) &&
		!selectedResources.includes(search.trim());

	return (
		<Combobox>
			<ComboboxTrigger selected={selectedResources.length > 0}>
				{renderSelectedResources()}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search resources..."
					onKeyDown={handleKeyDown}
				/>
				<ComboboxCommandList>
					<ComboboxCommandEmtpy>
						{search.trim() ? (
							<button
								type="button"
								className="w-full text-left px-2 py-1.5 text-sm hover:bg-accent rounded cursor-pointer"
								onClick={handleAddCustomResource}
							>
								Add &quot;{search.trim()}&quot;
							</button>
						) : (
							"No resources found"
						)}
					</ComboboxCommandEmtpy>
					{showAddCustomOption && (
						<ComboboxCommandGroup>
							<ComboboxCommandItem
								key={`add-${search.trim()}`}
								onSelect={handleAddCustomResource}
								value={`add-custom-${search.trim()}`}
								closeOnSelect={false}
							>
								Add &quot;{search.trim()}&quot;
							</ComboboxCommandItem>
						</ComboboxCommandGroup>
					)}
					{filteredGroups.map((group) => (
						<ComboboxCommandGroup key={group.label} heading={group.label}>
							{group.options.map((option) => (
								<ComboboxCommandItem
									key={option.value}
									selected={selectedResources.includes(option.value)}
									onSelect={() => handleResourceToggle(option.value)}
									value={option.value}
									closeOnSelect={false}
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
