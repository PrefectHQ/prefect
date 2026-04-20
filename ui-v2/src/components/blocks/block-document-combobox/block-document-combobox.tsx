import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useDeferredValue, useMemo, useState } from "react";
import { buildListFilterBlockDocumentsQuery } from "@/api/block-documents";
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
		<Suspense>
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

	const { data } = useSuspenseQuery(
		buildListFilterBlockDocumentsQuery({
			offset: 0,
			sort: "BLOCK_TYPE_AND_NAME_ASC",
			include_secrets: false,
			block_types: {
				slug: { any_: [blockTypeSlug] },
			},
			block_documents: {
				operator: "and_",
				is_anonymous: { eq_: false },
				...(deferredSearch ? { name: { like_: deferredSearch } } : {}),
			},
			limit: 50,
		}),
	);

	const filteredData = useMemo(() => {
		return data.filter((blockDocument) =>
			blockDocument.name?.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [data, deferredSearch]);

	const selectedBlockDocument = useMemo(() => {
		return data.find(
			(blockDocument) => blockDocument.id === selectedBlockDocumentId,
		);
	}, [data, selectedBlockDocumentId]);

	return (
		<Combobox>
			<ComboboxTrigger
				selected={Boolean(selectedBlockDocumentId)}
				aria-label="Select a block"
			>
				{selectedBlockDocument?.name ?? "Select a block..."}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search for a block..."
				/>
				<ComboboxCommandEmtpy>No block found</ComboboxCommandEmtpy>
				<ComboboxCommandList>
					<ComboboxCommandGroup>
						{filteredData.map((blockDocument) => (
							<ComboboxCommandItem
								key={blockDocument.id}
								selected={selectedBlockDocumentId === blockDocument.id}
								onSelect={(value) => {
									onSelect(value);
									setSearch("");
								}}
								value={blockDocument.id}
							>
								{blockDocument.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
					{onCreateNew && (
						<ComboboxCommandGroup>
							<ComboboxCommandItem
								onSelect={() => {
									onCreateNew();
									setSearch("");
								}}
								value="__create_new__"
								closeOnSelect={true}
							>
								<Icon id="Plus" className="mr-2 size-4" />
								Create new block
							</ComboboxCommandItem>
						</ComboboxCommandGroup>
					)}
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};
