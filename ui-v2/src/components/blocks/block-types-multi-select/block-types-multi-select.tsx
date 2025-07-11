"use client";

import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useDeferredValue, useMemo, useState } from "react";
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

type BlockTypesMultiSelectProps = {
	selectedBlockTypesSlugs: Array<string>;
	onToggleBlockTypeSlug: (blockTypeSlug: string) => void;
	onRemoveBlockTypeSlug: (blockTypeSlug: string) => void;
};

export function BlockTypesMultiSelect({
	selectedBlockTypesSlugs,
	onToggleBlockTypeSlug,
	onRemoveBlockTypeSlug,
}: BlockTypesMultiSelectProps) {
	return (
		<Suspense>
			<BlockTypesMultiSelectImplementation
				selectedBlockTypesSlugs={selectedBlockTypesSlugs}
				onToggleBlockTypeSlug={onToggleBlockTypeSlug}
				onRemoveBlockTypeSlug={onRemoveBlockTypeSlug}
			/>
		</Suspense>
	);
}

function BlockTypesMultiSelectImplementation({
	selectedBlockTypesSlugs,
	onToggleBlockTypeSlug,
	onRemoveBlockTypeSlug,
}: BlockTypesMultiSelectProps) {
	const [search, setSearch] = useState("");

	const deferredSearch = useDeferredValue(search);

	const { data: blockTypes } = useSuspenseQuery(
		buildListFilterBlockTypesQuery(),
	);

	const selectedBlockTypes = useMemo(() => {
		return selectedBlockTypesSlugs
			.map((blockTypeSlug) =>
				blockTypes.find((blockType) => blockType.slug === blockTypeSlug),
			)
			.filter(Boolean) as Array<BlockType>;
	}, [blockTypes, selectedBlockTypesSlugs]);

	const filteredData = useMemo(() => {
		return blockTypes.filter((blockType) =>
			blockType.name.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [blockTypes, deferredSearch]);

	return (
		<Combobox>
			<ComboboxTrigger selected={selectedBlockTypesSlugs.length > 0}>
				<div className="flex gap-1">
					{selectedBlockTypesSlugs.length > 0
						? selectedBlockTypes.map((blockType) => (
								<TagBadge
									key={blockType.id}
									tag={blockType.name}
									onRemove={() => onRemoveBlockTypeSlug(blockType.slug)}
								/>
							))
						: "Select blocks"}
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
								selected={selectedBlockTypesSlugs.includes(blockType.slug)}
								onSelect={(value) => {
									onToggleBlockTypeSlug(value);
									setSearch("");
								}}
								value={blockType.slug}
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
