import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";
import {
	buildFilterWorkPoolsQuery,
	type WorkPool,
} from "@/api/work-pools/work-pools";
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

const MAX_WORK_POOLS_DISPLAYED = 2;

type WorkPoolFilterProps = {
	selectedWorkPools: Set<string>;
	onSelectWorkPools: (workPools: Set<string>) => void;
};

export const WorkPoolFilter = ({
	selectedWorkPools,
	onSelectWorkPools,
}: WorkPoolFilterProps) => {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const { data: workPools = [] } = useQuery(
		buildFilterWorkPoolsQuery({
			limit: 100,
			offset: 0,
		}),
	);

	const handleSelectWorkPool = (workPoolName: string) => {
		const updatedWorkPools = new Set(selectedWorkPools);
		if (selectedWorkPools.has(workPoolName)) {
			updatedWorkPools.delete(workPoolName);
		} else {
			updatedWorkPools.add(workPoolName);
		}
		onSelectWorkPools(updatedWorkPools);
	};

	const handleClearAll = () => {
		onSelectWorkPools(new Set());
	};

	const renderSelectedWorkPools = () => {
		if (selectedWorkPools.size === 0) {
			return "All work pools";
		}

		const selectedWorkPoolNames = Array.from(selectedWorkPools).sort((a, b) =>
			a.localeCompare(b),
		);

		const visible = selectedWorkPoolNames.slice(0, MAX_WORK_POOLS_DISPLAYED);
		const extraCount = selectedWorkPoolNames.length - MAX_WORK_POOLS_DISPLAYED;

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

	const filteredWorkPools = useMemo(() => {
		return workPools
			.filter(
				(workPool: WorkPool) =>
					!deferredSearch ||
					workPool.name.toLowerCase().includes(deferredSearch.toLowerCase()),
			)
			.sort((a: WorkPool, b: WorkPool) => a.name.localeCompare(b.name));
	}, [workPools, deferredSearch]);

	return (
		<Combobox>
			<ComboboxTrigger
				aria-label="Filter by work pool"
				selected={selectedWorkPools.size === 0}
			>
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
						<ComboboxCommandItem
							aria-label="All work pools"
							onSelect={handleClearAll}
							closeOnSelect={false}
							value="__all__"
						>
							<Checkbox checked={selectedWorkPools.size === 0} />
							All work pools
						</ComboboxCommandItem>
						{filteredWorkPools.map((workPool: WorkPool) => (
							<ComboboxCommandItem
								key={workPool.name}
								aria-label={workPool.name}
								onSelect={() => handleSelectWorkPool(workPool.name)}
								closeOnSelect={false}
								value={workPool.name}
							>
								<Checkbox checked={selectedWorkPools.has(workPool.name)} />
								{workPool.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
