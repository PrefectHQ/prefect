import { Link } from "@tanstack/react-router";
import type { BlockDocument } from "@/api/block-documents";
import { BlockTypeLogo } from "@/components/block-type-logo/block-type-logo";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icons";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

type DefaultResultStorageCardProps = {
	defaultResultStorageBlockId: string | undefined;
	defaultResultStorageBlock: BlockDocument | undefined;
	storageBlockDocuments: Array<BlockDocument> | undefined;
	onUpdateDefaultResultStorage: (blockDocumentId: string) => void;
	onClearDefaultResultStorage: () => void;
	isUpdatingDefaultResultStorage: boolean;
	isClearingDefaultResultStorage: boolean;
	isLoadingDefaultResultStorageBlock: boolean;
};

export const DefaultResultStorageCard = ({
	defaultResultStorageBlockId,
	defaultResultStorageBlock,
	storageBlockDocuments = [],
	onUpdateDefaultResultStorage,
	onClearDefaultResultStorage,
	isUpdatingDefaultResultStorage,
	isClearingDefaultResultStorage,
	isLoadingDefaultResultStorageBlock,
}: DefaultResultStorageCardProps) => {
	const isMutating =
		isUpdatingDefaultResultStorage || isClearingDefaultResultStorage;
	const hasConfiguredMissingBlock =
		Boolean(defaultResultStorageBlockId) &&
		!defaultResultStorageBlock &&
		!isLoadingDefaultResultStorageBlock;

	return (
		<Card className="gap-4 p-4">
			<div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
				<div className="flex min-w-0 flex-1 flex-col gap-3">
					<div className="flex flex-wrap items-center gap-2">
						<h2 className="text-base font-semibold">Default result storage</h2>
						{defaultResultStorageBlockId ? (
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
						<div className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
							{isLoadingDefaultResultStorageBlock &&
								"Loading configured storage block..."}
							{hasConfiguredMissingBlock &&
								"The configured default storage block could not be found."}
							{!defaultResultStorageBlockId &&
								"No default storage block is configured."}
						</div>
					)}
				</div>
				<div className="flex w-full flex-col gap-2 lg:w-80">
					<Select
						value={defaultResultStorageBlockId}
						onValueChange={onUpdateDefaultResultStorage}
						disabled={isMutating || storageBlockDocuments.length === 0}
					>
						<SelectTrigger aria-label="Default result storage block">
							<SelectValue placeholder="Select storage block" />
						</SelectTrigger>
						<SelectContent>
							{storageBlockDocuments.map((blockDocument) => (
								<SelectItem key={blockDocument.id} value={blockDocument.id}>
									{blockDocument.name ?? "Untitled block"}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
					<div className="flex flex-wrap gap-2">
						<Button variant="outline" size="sm" asChild>
							<Link to="/blocks/catalog">
								<Icon id="Plus" className="size-4" />
								New storage block
							</Link>
						</Button>
						<Button
							variant="outline"
							size="sm"
							onClick={onClearDefaultResultStorage}
							disabled={!defaultResultStorageBlockId || isMutating}
						>
							<Icon id="X" className="size-4" />
							Clear
						</Button>
					</div>
				</div>
			</div>
		</Card>
	);
};

const DefaultResultStorageBlock = ({
	blockDocument,
}: {
	blockDocument: BlockDocument;
}) => {
	const blockTypeName =
		blockDocument.block_type_name ?? blockDocument.block_type?.name;

	return (
		<Link to="/blocks/block/$id" params={{ id: blockDocument.id }}>
			<div className="flex items-center gap-3 rounded-lg border bg-muted/40 p-3 transition-colors hover:bg-muted">
				{blockDocument.block_type && blockTypeName ? (
					<BlockTypeLogo
						size="sm"
						logoUrl={blockDocument.block_type.logo_url}
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
