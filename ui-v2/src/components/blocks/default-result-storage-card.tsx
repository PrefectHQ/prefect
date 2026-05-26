import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Suspense, useDeferredValue, useMemo, useState } from "react";
import {
	type BlockDocument,
	buildListFilterBlockDocumentsQuery,
} from "@/api/block-documents";
import { BlockTypeLogo } from "@/components/block-type-logo/block-type-logo";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { Icon } from "@/components/ui/icons";

type DefaultResultStorageCardProps = {
	defaultResultStorageBlockId: string | undefined;
	defaultResultStorageBlock: BlockDocument | undefined;
	onUpdateDefaultResultStorage: (blockDocumentId: string) => void;
	onClearDefaultResultStorage: () => void;
	isUpdatingDefaultResultStorage: boolean;
	isClearingDefaultResultStorage: boolean;
	isLoadingDefaultResultStorageBlock: boolean;
};

export const DefaultResultStorageCard = ({
	defaultResultStorageBlockId,
	defaultResultStorageBlock,
	onUpdateDefaultResultStorage,
	onClearDefaultResultStorage,
	isUpdatingDefaultResultStorage,
	isClearingDefaultResultStorage,
	isLoadingDefaultResultStorageBlock,
}: DefaultResultStorageCardProps) => {
	const isMutating =
		isUpdatingDefaultResultStorage || isClearingDefaultResultStorage;
	const statusState = isLoadingDefaultResultStorageBlock
		? "loading"
		: defaultResultStorageBlock
			? undefined
			: "empty";
	const hasVisibleDefaultResultStorage =
		Boolean(defaultResultStorageBlock) || isLoadingDefaultResultStorageBlock;
	const canClearDefaultResultStorage = Boolean(defaultResultStorageBlock);

	return (
		<Card className="p-4">
			<div className="flex max-w-3xl flex-col gap-3">
				<div className="flex min-w-0 flex-col gap-3">
					<div className="flex flex-wrap items-center gap-2">
						<h2 className="text-base font-semibold">Default result storage</h2>
						{hasVisibleDefaultResultStorage ? (
							<Badge variant="secondary">Configured</Badge>
						) : (
							<Badge variant="outline">Not configured</Badge>
						)}
					</div>
					<p className="max-w-3xl text-sm text-muted-foreground">
						Persisted flow and task return values use this storage block when
						runs do not set result storage explicitly.
					</p>
					{defaultResultStorageBlock ? (
						<DefaultResultStorageBlock
							blockDocument={defaultResultStorageBlock}
						/>
					) : (
						<DefaultResultStorageStatus state={statusState} />
					)}
				</div>
				<div className="flex flex-col gap-2 sm:flex-row sm:items-center">
					<div className="w-full sm:w-64">
						<StorageBlockCombobox
							selectedBlockDocumentId={defaultResultStorageBlockId}
							selectedBlockDocumentName={defaultResultStorageBlock?.name}
							onSelect={onUpdateDefaultResultStorage}
							isMutating={isMutating}
						/>
					</div>
					<div className="flex flex-wrap gap-2">
						<Button variant="outline" size="sm" asChild>
							<Link to="/blocks/catalog">
								<Icon id="Plus" className="size-4" />
								New storage block
							</Link>
						</Button>
						{canClearDefaultResultStorage && (
							<Button
								variant="outline"
								size="sm"
								onClick={onClearDefaultResultStorage}
								disabled={isMutating}
							>
								<Icon id="X" className="size-4" />
								Clear
							</Button>
						)}
					</div>
				</div>
			</div>
		</Card>
	);
};

type StorageBlockComboboxProps = {
	selectedBlockDocumentId: string | undefined;
	selectedBlockDocumentName: string | null | undefined;
	onSelect: (blockDocumentId: string) => void;
	isMutating?: boolean;
};

const StorageBlockComboboxFallback = ({
	selectedBlockDocumentName,
}: {
	selectedBlockDocumentName: string | null | undefined;
}) => (
	<div className="flex h-9 w-full items-center justify-between rounded-md border bg-card px-4 py-2 text-sm text-muted-foreground opacity-50 dark:bg-background">
		{selectedBlockDocumentName ?? "Select storage block..."}
		<Icon id="ChevronsUpDown" className="size-4 opacity-50" />
	</div>
);

const StorageBlockCombobox = (props: StorageBlockComboboxProps) => {
	return (
		<ErrorBoundary
			fallback={
				<StorageBlockComboboxFallback
					selectedBlockDocumentName={props.selectedBlockDocumentName}
				/>
			}
		>
			<Suspense
				fallback={
					<div className="h-9 w-full animate-pulse rounded-md border bg-muted/30" />
				}
			>
				<StorageBlockComboboxImpl {...props} />
			</Suspense>
		</ErrorBoundary>
	);
};

const StorageBlockComboboxImpl = ({
	selectedBlockDocumentId,
	selectedBlockDocumentName,
	onSelect,
	isMutating = false,
}: StorageBlockComboboxProps) => {
	const [search, setSearch] = useState("");
	const deferredSearch = useDeferredValue(search);

	const { data } = useSuspenseQuery(
		buildListFilterBlockDocumentsQuery({
			offset: 0,
			sort: "BLOCK_TYPE_AND_NAME_ASC",
			include_secrets: false,
			block_documents: {
				operator: "and_",
				is_anonymous: { eq_: false },
				...(deferredSearch ? { name: { like_: deferredSearch } } : {}),
			},
			block_schemas: {
				operator: "and_",
				block_capabilities: { all_: ["write-path"] },
			},
			limit: 50,
		}),
	);

	const filteredData = useMemo(() => {
		if (!deferredSearch) {
			return data;
		}
		return data.filter((blockDocument) =>
			(blockDocument.name ?? "")
				.toLowerCase()
				.includes(deferredSearch.toLowerCase()),
		);
	}, [data, deferredSearch]);

	const displayName =
		filteredData.find((d) => d.id === selectedBlockDocumentId)?.name ??
		selectedBlockDocumentName;

	return (
		<Combobox>
			<ComboboxTrigger
				selected={Boolean(selectedBlockDocumentId)}
				aria-label="Default result storage block"
			>
				{displayName ?? "Select storage block..."}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search storage blocks..."
				/>
				<ComboboxCommandEmtpy>No storage blocks found</ComboboxCommandEmtpy>
				<ComboboxCommandList>
					<ComboboxCommandGroup>
						{filteredData.map((blockDocument) => (
							<ComboboxCommandItem
								key={blockDocument.id}
								disabled={isMutating}
								selected={selectedBlockDocumentId === blockDocument.id}
								onSelect={(value) => {
									if (!isMutating) {
										onSelect(value);
									}
									setSearch("");
								}}
								value={blockDocument.id}
							>
								{blockDocument.name ?? "Untitled block"}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
};

const DefaultResultStorageBlock = ({
	blockDocument,
}: {
	blockDocument: BlockDocument;
}) => {
	const blockTypeName =
		blockDocument.block_type_name ?? blockDocument.block_type?.name;
	const logoUrl = blockDocument.block_type?.logo_url;

	return (
		<Link to="/blocks/block/$id" params={{ id: blockDocument.id }}>
			<div className="flex items-center gap-3 rounded-lg border bg-muted/40 p-3 transition-colors hover:bg-muted">
				{logoUrl && blockTypeName ? (
					<BlockTypeLogo
						size="sm"
						logoUrl={logoUrl}
						alt={`${blockTypeName} logo`}
					/>
				) : (
					<div className="flex size-8 items-center justify-center rounded border bg-muted">
						<Icon id="Box" className="size-4 text-muted-foreground" />
					</div>
				)}
				<div className="min-w-0">
					<div className="truncate text-sm font-medium">
						{blockDocument.name ?? "Untitled block"}
					</div>
					{blockTypeName && (
						<div className="truncate text-sm text-muted-foreground">
							{blockTypeName}
						</div>
					)}
				</div>
			</div>
		</Link>
	);
};

const DefaultResultStorageStatus = ({
	state,
}: {
	state: "empty" | "loading" | undefined;
}) => {
	if (state === "loading") {
		return (
			<div className="flex items-center gap-3 rounded-lg border bg-muted/30 p-3 text-sm text-muted-foreground">
				<div className="flex size-8 items-center justify-center rounded border bg-background">
					<Icon id="Loader2" className="size-4 animate-spin" />
				</div>
				Loading configured storage block...
			</div>
		);
	}

	return (
		<div className="flex items-center gap-3 rounded-lg border border-dashed bg-muted/20 p-3 text-sm text-muted-foreground">
			<div className="flex size-8 items-center justify-center rounded border bg-background">
				<Icon id="Box" className="size-4" />
			</div>
			No default storage block is configured.
		</div>
	);
};
