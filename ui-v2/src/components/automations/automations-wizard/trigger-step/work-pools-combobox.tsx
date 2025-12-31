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

type WorkPoolsComboboxProps = {
	selectedWorkPoolIds: string[];
	onToggleWorkPool: (workPoolId: string) => void;
	emptyMessage?: string;
};

export function WorkPoolsCombobox({
	selectedWorkPoolIds,
	onToggleWorkPool,
	emptyMessage = "All work pools",
}: WorkPoolsComboboxProps) {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const { data: workPools = [] } = useQuery(
		buildFilterWorkPoolsQuery({
			limit: 100,
			offset: 0,
		}),
	);

	const filteredWorkPools = useMemo(() => {
		return workPools.filter((workPool: WorkPool) => {
			if (!workPool.status) {
				return false;
			}
			if (!deferredSearch) {
				return true;
			}
			return workPool.name.toLowerCase().includes(deferredSearch.toLowerCase());
		});
	}, [workPools, deferredSearch]);

	const renderSelectedWorkPools = () => {
		if (selectedWorkPoolIds.length === 0) {
			return <span className="text-muted-foreground">{emptyMessage}</span>;
		}

		const selectedWorkPoolNames = workPools
			.filter((workPool) => selectedWorkPoolIds.includes(workPool.id))
			.map((workPool) => workPool.name);

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
