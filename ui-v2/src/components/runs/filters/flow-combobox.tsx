import { useMemo, useState } from "react";
import type { Flow } from "@/api/flows";
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

type FlowComboboxProps = {
	flows: Flow[];
	selectedFlowIds: string[];
	onSelectFlows: (flowIds: string[]) => void;
};

export const FlowCombobox = ({
	flows,
	selectedFlowIds,
	onSelectFlows,
}: FlowComboboxProps) => {
	const [search, setSearch] = useState("");

	const selectedSet = useMemo(
		() => new Set(selectedFlowIds),
		[selectedFlowIds],
	);

	const filteredFlows = useMemo(() => {
		if (!search) return flows;
		const lowerSearch = search.toLowerCase();
		return flows.filter((flow) =>
			flow.name.toLowerCase().includes(lowerSearch),
		);
	}, [flows, search]);

	const handleSelect = (flowId: string) => {
		const updatedSet = new Set(selectedSet);
		if (selectedSet.has(flowId)) {
			updatedSet.delete(flowId);
		} else {
			updatedSet.add(flowId);
		}
		onSelectFlows(Array.from(updatedSet));
	};

	const getDisplayText = () => {
		if (selectedFlowIds.length === 0) {
			return "All flows";
		}
		if (selectedFlowIds.length === 1) {
			const flow = flows.find((f) => f.id === selectedFlowIds[0]);
			return flow?.name ?? "1 flow";
		}
		return `${selectedFlowIds.length} flows`;
	};

	return (
		<Combobox>
			<ComboboxTrigger
				aria-label="Filter by flow"
				selected={selectedFlowIds.length === 0}
			>
				{getDisplayText()}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					placeholder="Search flows..."
					value={search}
					onValueChange={setSearch}
				/>
				<ComboboxCommandList>
					<ComboboxCommandEmtpy>No flows found</ComboboxCommandEmtpy>
					<ComboboxCommandGroup>
						{filteredFlows.map((flow) => (
							<ComboboxCommandItem
								key={flow.id}
								value={flow.id}
								onSelect={handleSelect}
								selected={selectedSet.has(flow.id)}
								closeOnSelect={false}
							>
								{flow.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
