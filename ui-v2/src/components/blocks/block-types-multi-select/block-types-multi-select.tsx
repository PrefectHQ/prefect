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

import { TagBadgeGroupX } from "@/components/ui/tag-badge-group";
import { useSet } from "@/hooks/use-set";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useDeferredValue, useMemo, useState } from "react";

export function BlockTypesMultiSelect() {
	return (
		<Suspense>
			<BlockTypesMultiSelectImplementation />
		</Suspense>
	);
}

function BlockTypesMultiSelectImplementation() {
	const [search, setSearch] = useState("");
	const [selectedBlockTypesIds, setSet, { toggle, has }] = useSet();

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

	const handleRemoveTag = (blockTypes: Array<BlockType>) => {
		const blockTypeIds = blockTypes.map((blockType) => blockType.id);
		setSet(new Set(blockTypeIds));
	};

	return (
		<Combobox>
			<ComboboxTrigger selected={selectedBlockTypesIds.size > 0}>
				<div className="flex gap-1">
					{selectedBlockTypesIds.size > 0 ? (
						<TagBadgeGroupX
							tags={selectedBlockTypes}
							idKey="id"
							labelKey="name"
							onTagsChange={handleRemoveTag}
						/>
					) : (
						"Select block types"
					)}
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
								selected={has(blockType.id)}
								onSelect={(value) => {
									toggle(value);
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
