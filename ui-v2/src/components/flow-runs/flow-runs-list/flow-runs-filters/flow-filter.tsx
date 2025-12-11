import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";
import { buildListFlowsQuery, type Flow } from "@/api/flows";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Typography } from "@/components/ui/typography";

const MAX_FLOWS_DISPLAYED = 2;

type FlowFilterProps = {
	selectedFlows: Set<string>;
	onSelectFlows: (flows: Set<string>) => void;
};

export const FlowFilter = ({
	selectedFlows,
	onSelectFlows,
}: FlowFilterProps) => {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const { data: flows = [] } = useQuery(
		buildListFlowsQuery({
			flows: deferredSearch
				? {
						operator: "and_",
						name: { like_: deferredSearch },
					}
				: undefined,
			limit: 100,
			offset: 0,
			sort: "NAME_ASC",
		}),
	);

	const { data: selectedFlowsData = [] } = useQuery(
		buildListFlowsQuery(
			{
				flows:
					selectedFlows.size > 0
						? {
								operator: "and_",
								id: { any_: Array.from(selectedFlows) },
							}
						: undefined,
				limit: selectedFlows.size || 1,
				offset: 0,
				sort: "NAME_ASC",
			},
			{ enabled: selectedFlows.size > 0 },
		),
	);

	const handleSelectFlow = (flowId: string) => {
		const updatedFlows = new Set(selectedFlows);
		if (selectedFlows.has(flowId)) {
			updatedFlows.delete(flowId);
		} else {
			updatedFlows.add(flowId);
		}
		onSelectFlows(updatedFlows);
	};

	const handleClearAll = () => {
		onSelectFlows(new Set());
	};

	const renderSelectedFlows = () => {
		if (selectedFlows.size === 0) {
			return "All flows";
		}

		const selectedFlowNames = selectedFlowsData
			.filter((flow) => selectedFlows.has(flow.id))
			.map((flow) => flow.name);

		const visible = selectedFlowNames.slice(0, MAX_FLOWS_DISPLAYED);
		const extraCount = selectedFlowNames.length - MAX_FLOWS_DISPLAYED;

		return (
			<div className="flex flex-1 min-w-0 items-center gap-2">
				<div className="flex flex-1 min-w-0 items-center gap-2 overflow-hidden">
					<span className="truncate">{visible.join(", ")}</span>
				</div>
				{extraCount > 0 && (
					<Typography variant="bodySmall" className="shrink-0">
						+ {extraCount}
					</Typography>
				)}
			</div>
		);
	};

	const filteredFlows = useMemo(() => {
		return flows.filter(
			(flow: Flow) =>
				!deferredSearch ||
				flow.name.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [flows, deferredSearch]);

	return (
		<Combobox>
			<ComboboxTrigger
				aria-label="Filter by flow"
				selected={selectedFlows.size === 0}
			>
				{renderSelectedFlows()}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search flows..."
				/>
				<ComboboxCommandList>
					<ComboboxCommandEmtpy>No flows found</ComboboxCommandEmtpy>
					<ComboboxCommandGroup>
						<ComboboxCommandItem
							aria-label="All flows"
							onSelect={handleClearAll}
							closeOnSelect={false}
							value="__all__"
						>
							<Checkbox checked={selectedFlows.size === 0} />
							All flows
						</ComboboxCommandItem>
						{filteredFlows.map((flow: Flow) => (
							<ComboboxCommandItem
								key={flow.id}
								aria-label={flow.name}
								onSelect={() => handleSelectFlow(flow.id)}
								closeOnSelect={false}
								value={flow.id}
							>
								<Checkbox checked={selectedFlows.has(flow.id)} />
								{flow.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
