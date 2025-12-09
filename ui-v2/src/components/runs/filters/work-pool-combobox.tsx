import { useMemo, useState } from "react";
import type { WorkPool } from "@/api/work-pools";
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

type WorkPoolComboboxProps = {
	workPools: WorkPool[];
	selectedWorkPoolNames: string[];
	onSelectWorkPools: (workPoolNames: string[]) => void;
};

export const WorkPoolCombobox = ({
	workPools,
	selectedWorkPoolNames,
	onSelectWorkPools,
}: WorkPoolComboboxProps) => {
	const [search, setSearch] = useState("");

	const selectedSet = useMemo(
		() => new Set(selectedWorkPoolNames),
		[selectedWorkPoolNames],
	);

	const filteredWorkPools = useMemo(() => {
		if (!search) return workPools;
		const lowerSearch = search.toLowerCase();
		return workPools.filter((workPool) =>
			workPool.name.toLowerCase().includes(lowerSearch),
		);
	}, [workPools, search]);

	const handleSelect = (workPoolName: string) => {
		const updatedSet = new Set(selectedSet);
		if (selectedSet.has(workPoolName)) {
			updatedSet.delete(workPoolName);
		} else {
			updatedSet.add(workPoolName);
		}
		onSelectWorkPools(Array.from(updatedSet));
	};

	const getDisplayText = () => {
		if (selectedWorkPoolNames.length === 0) {
			return "All work pools";
		}
		if (selectedWorkPoolNames.length === 1) {
			return selectedWorkPoolNames[0];
		}
		return `${selectedWorkPoolNames.length} work pools`;
	};

	return (
		<Combobox>
			<ComboboxTrigger
				aria-label="Filter by work pool"
				selected={selectedWorkPoolNames.length === 0}
			>
				{getDisplayText()}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					placeholder="Search work pools..."
					value={search}
					onValueChange={setSearch}
				/>
				<ComboboxCommandList>
					<ComboboxCommandEmtpy>No work pools found</ComboboxCommandEmtpy>
					<ComboboxCommandGroup>
						{filteredWorkPools.map((workPool) => (
							<ComboboxCommandItem
								key={workPool.name}
								value={workPool.name}
								onSelect={handleSelect}
								selected={selectedSet.has(workPool.name)}
								closeOnSelect={false}
							>
								{workPool.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
