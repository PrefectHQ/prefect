import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useDeferredValue, useMemo, useState } from "react";
import { buildListFilterBlockDocumentsQuery } from "@/api/block-documents";
import { buildGetBlockTypeQuery } from "@/api/block-types";
import { Button } from "@/components/ui/button";
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
import { Icon } from "@/components/ui/icons";

type BlockDocumentComboboxProps = {
	blockTypeSlug: string;
	selectedBlockDocumentId: string | undefined;
	onSelect: (blockDocumentId: string | undefined) => void;
	onCreateNew?: () => void;
};

export const BlockDocumentCombobox = ({
	blockTypeSlug,
	selectedBlockDocumentId,
	onSelect,
	onCreateNew,
}: BlockDocumentComboboxProps) => {
	return (
		<Suspense
			fallback={<div className="h-10 animate-pulse bg-muted rounded" />}
		>
			<BlockDocumentComboboxImplementation
				blockTypeSlug={blockTypeSlug}
				selectedBlockDocumentId={selectedBlockDocumentId}
				onSelect={onSelect}
				onCreateNew={onCreateNew}
			/>
		</Suspense>
	);
};

const BlockDocumentComboboxImplementation = ({
	blockTypeSlug,
	selectedBlockDocumentId,
	onSelect,
	onCreateNew,
}: BlockDocumentComboboxProps) => {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const { data: blockType } = useSuspenseQuery(
		buildGetBlockTypeQuery(blockTypeSlug),
	);

	const { data: blockDocuments } = useSuspenseQuery(
		buildListFilterBlockDocumentsQuery({
			block_types: {
				slug: {
					any_: [blockTypeSlug],
				},
			},
			block_documents: {
				operator: "and_",
				is_anonymous: { eq_: false },
				...(deferredSearch
					? {
							name: {
								like_: deferredSearch,
							},
						}
					: {}),
			},
			offset: 0,
			limit: 50,
			include_secrets: false,
		}),
	);

	const filteredData = useMemo(() => {
		return blockDocuments.filter((doc) =>
			doc.name?.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [blockDocuments, deferredSearch]);

	const selectedBlockDocument = useMemo(() => {
		return blockDocuments.find((doc) => doc.id === selectedBlockDocumentId);
	}, [blockDocuments, selectedBlockDocumentId]);

	const displayName =
		selectedBlockDocument?.name ?? `Select a ${blockType.name}...`;

	return (
		<Combobox>
			<ComboboxTrigger
				selected={Boolean(selectedBlockDocumentId)}
				aria-label={`Select a ${blockType.name}`}
			>
				{displayName}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder={`Search for a ${blockType.name}...`}
				/>
				<ComboboxCommandEmtpy>No block document found</ComboboxCommandEmtpy>
				<ComboboxCommandList>
					<ComboboxCommandGroup>
						{filteredData.map((doc) => (
							<ComboboxCommandItem
								key={doc.id}
								selected={selectedBlockDocumentId === doc.id}
								onSelect={() => {
									onSelect(doc.id);
									setSearch("");
								}}
								value={doc.id}
							>
								{doc.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
					{onCreateNew && (
						<ComboboxCommandGroup>
							<Button
								variant="ghost"
								className="w-full justify-start"
								onClick={onCreateNew}
							>
								<Icon id="Plus" className="mr-2 size-4" />
								Create new {blockType.name}
							</Button>
						</ComboboxCommandGroup>
					)}
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
