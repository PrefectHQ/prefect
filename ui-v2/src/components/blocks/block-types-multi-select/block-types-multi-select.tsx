"use client";

import {
	type BlockType,
	buildListFilterBlockTypesQuery,
} from "@/api/block-types";

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
import { TagBadge } from "@/components/ui/tag-badge";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useDeferredValue, useMemo, useState } from "react";

type BlockTypesMultiSelectProps = {
	selectedBlockTypesIds: Set<string>;
	onToggleBlockType: (blockTypeIds: string) => void;
	onRemoveBlockType: (blockTypeIds: string) => void;
};

export function BlockTypesMultiSelect({
	selectedBlockTypesIds,
	onToggleBlockType,
	onRemoveBlockType,
}: BlockTypesMultiSelectProps) {
	return (
		<Suspense>
			<BlockTypesMultiSelectImplementation
				selectedBlockTypesIds={selectedBlockTypesIds}
				onToggleBlockType={onToggleBlockType}
				onRemoveBlockType={onRemoveBlockType}
			/>
		</Suspense>
	);
}

function BlockTypesMultiSelectImplementation({
	selectedBlockTypesIds,
	onToggleBlockType,
	onRemoveBlockType,
}: BlockTypesMultiSelectProps) {
	const [search, setSearch] = useState("");

	const deferredSearch = useDeferredValue(search);

	const { data: blockTypes } = useSuspenseQuery(
		buildListFilterBlockTypesQuery(),
	);

	const selectedBlockTypes = useMemo(() => {
		return Array.from(selectedBlockTypesIds)
			.map((blockTypeId) =>
				blockTypes.find((blockType) => blockType.id === blockTypeId),
			)
			.filter(Boolean) as Array<BlockType>;
	}, [blockTypes, selectedBlockTypesIds]);

	const filteredData = useMemo(() => {
		return blockTypes.filter((blockType) =>
			blockType.name.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [blockTypes, deferredSearch]);

	return (
		<Combobox>
			<ComboboxTrigger selected={selectedBlockTypesIds.size > 0}>
				<div className="flex gap-1">
					{selectedBlockTypesIds.size > 0
						? selectedBlockTypes.map((blockType) => (
								<TagBadge
									key={blockType.id}
									tag={blockType.name}
									onRemove={() => onRemoveBlockType(blockType.id)}
								/>
							))
						: "Select block types"}
				</div>
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search for a block type..."
				/>
				<ComboboxCommandEmtpy>No block type found</ComboboxCommandEmtpy>
				<ComboboxCommandList>
					<ComboboxCommandGroup>
						{filteredData.map((blockType) => (
							<ComboboxCommandItem
								key={blockType.id}
								selected={selectedBlockTypesIds.has(blockType.id)}
								onSelect={(value) => {
									onToggleBlockType(value);
									setSearch("");
								}}
								value={blockType.id}
							>
								{blockType.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}
