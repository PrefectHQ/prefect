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

const MAX_VISIBLE_FLOWS = 2;

type FlowMultiSelectProps = {
	selectedFlowIds: string[];
	onSelectFlowIds: (flowIds: string[]) => void;
	emptyMessage?: string;
};

export function FlowMultiSelect({
	selectedFlowIds,
	onSelectFlowIds,
	emptyMessage = "Any flow",
}: FlowMultiSelectProps) {
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
					selectedFlowIds.length > 0
						? {
								operator: "and_",
								id: { any_: selectedFlowIds },
							}
						: undefined,
				limit: selectedFlowIds.length || 1,
				offset: 0,
				sort: "NAME_ASC",
			},
			{ enabled: selectedFlowIds.length > 0 },
		),
	);

	const filteredFlows = useMemo(() => {
		return flows.filter(
			(flow: Flow) =>
				!deferredSearch ||
				flow.name.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [flows, deferredSearch]);

	const renderSelectedFlows = () => {
		if (selectedFlowIds.length === 0) {
			return emptyMessage;
		}

		const selectedFlowNames = selectedFlowsData
			.filter((flow) => selectedFlowIds.includes(flow.id))
			.map((flow) => flow.name);

		const visibleNames = selectedFlowNames.slice(0, MAX_VISIBLE_FLOWS);
		const overflow = selectedFlowIds.length - visibleNames.length;

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

	return (
		<Combobox>
			<ComboboxTrigger selected={selectedFlowIds.length === 0}>
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
							aria-label={emptyMessage}
							onSelect={() => onSelectFlowIds([])}
							closeOnSelect={false}
							value="__all__"
						>
							<Checkbox checked={selectedFlowIds.length === 0} />
							{emptyMessage}
						</ComboboxCommandItem>
						{filteredFlows.map((flow: Flow) => (
							<ComboboxCommandItem
								key={flow.id}
								aria-label={flow.name}
								onSelect={() => {
									onSelectFlowIds(
										selectedFlowIds.includes(flow.id)
											? selectedFlowIds.filter((id) => id !== flow.id)
											: [...selectedFlowIds, flow.id],
									);
									setSearch("");
								}}
								closeOnSelect={false}
								value={flow.id}
							>
								<Checkbox checked={selectedFlowIds.includes(flow.id)} />
								{flow.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}
