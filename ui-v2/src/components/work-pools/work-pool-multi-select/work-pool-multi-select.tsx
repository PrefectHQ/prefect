import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";
import { buildFilterWorkPoolsQuery, type WorkPool } from "@/api/work-pools";
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

// Show all selected work pool names and let CSS truncation handle overflow

type WorkPoolMultiSelectProps = {
	selectedWorkPoolIds: string[];
	onToggleWorkPool: (workPoolId: string) => void;
	emptyMessage?: string;
};

export function WorkPoolMultiSelect({
	selectedWorkPoolIds,
	onToggleWorkPool,
	emptyMessage = "All work pools",
}: WorkPoolMultiSelectProps) {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const { data: workPools = [] } = useQuery(buildFilterWorkPoolsQuery());

	// Filter to only show work pools with a status (excluding push/agent pools)
	// and apply search filter
	const filteredWorkPools = useMemo(() => {
		return workPools
			.filter((workPool: WorkPool) => workPool.status !== null)
			.filter(
				(workPool: WorkPool) =>
					!deferredSearch ||
					workPool.name.toLowerCase().includes(deferredSearch.toLowerCase()),
			);
	}, [workPools, deferredSearch]);

	// Get selected work pools data for display
	const selectedWorkPoolsData = useMemo(() => {
		return workPools.filter((workPool: WorkPool) =>
			selectedWorkPoolIds.includes(workPool.id),
		);
	}, [workPools, selectedWorkPoolIds]);

	const renderSelectedWorkPools = () => {
		if (selectedWorkPoolIds.length === 0) {
			return <span className="text-muted-foreground">{emptyMessage}</span>;
		}

		const selectedWorkPoolNames = selectedWorkPoolsData.map(
			(workPool) => workPool.name,
		);

		// Show all names and let CSS truncation handle overflow
		return (
			<span className="truncate min-w-0 text-left">
				{selectedWorkPoolNames.join(", ")}
			</span>
		);
	};

	return (
		<Combobox>
			<ComboboxTrigger selected={selectedWorkPoolIds.length > 0}>
				{renderSelectedWorkPools()}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search work pools..."
				/>
				<ComboboxCommandList>
					<ComboboxCommandEmtpy>No work pools found</ComboboxCommandEmtpy>
					<ComboboxCommandGroup>
						{filteredWorkPools.map((workPool: WorkPool) => (
							<ComboboxCommandItem
								key={workPool.id}
								selected={selectedWorkPoolIds.includes(workPool.id)}
								onSelect={() => {
									onToggleWorkPool(workPool.id);
									setSearch("");
								}}
								closeOnSelect={false}
								value={workPool.id}
							>
								{workPool.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}
