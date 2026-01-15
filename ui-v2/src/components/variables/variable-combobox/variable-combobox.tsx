import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useDeferredValue, useMemo, useState } from "react";
import { buildFilterVariablesQuery } from "@/api/variables";
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

type VariableComboboxProps = {
	selectedVariableName: string | undefined;
	onSelect: (variableName: string | undefined) => void;
};

export const VariableCombobox = ({
	selectedVariableName,
	onSelect,
}: VariableComboboxProps) => {
	return (
		<Suspense>
			<VariableComboboxImplementation
				selectedVariableName={selectedVariableName}
				onSelect={onSelect}
			/>
		</Suspense>
	);
};

const VariableComboboxImplementation = ({
	selectedVariableName,
	onSelect,
}: VariableComboboxProps) => {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const { data } = useSuspenseQuery(
		buildFilterVariablesQuery({
			offset: 0,
			sort: "NAME_ASC",
			variables: deferredSearch
				? { operator: "and_", name: { like_: deferredSearch } }
				: undefined,
			limit: 50,
		}),
	);

	const filteredData = useMemo(() => {
		return data.filter((variable) =>
			variable.name.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [data, deferredSearch]);

	return (
		<Combobox>
			<ComboboxTrigger
				selected={Boolean(selectedVariableName)}
				aria-label="Select a variable"
			>
				{selectedVariableName ?? "Select a variable..."}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search for a variable..."
				/>
				<ComboboxCommandEmtpy>No variable found</ComboboxCommandEmtpy>
				<ComboboxCommandList>
					<ComboboxCommandGroup>
						{filteredData.map((variable) => (
							<ComboboxCommandItem
								key={variable.id}
								selected={selectedVariableName === variable.name}
								onSelect={(value) => {
									onSelect(value);
									setSearch("");
								}}
								value={variable.name}
							>
								{variable.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
