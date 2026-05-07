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
	const selectedBlockDocumentExists = storageBlockDocuments.some(
		(blockDocument) => blockDocument.id === defaultResultStorageBlockId,
	);
	const selectValue = selectedBlockDocumentExists
		? defaultResultStorageBlockId
		: undefined;
	const hasConfiguredMissingBlock =
		Boolean(defaultResultStorageBlockId) &&
		!defaultResultStorageBlock &&
		!isLoadingDefaultResultStorageBlock;
	const statusState = isLoadingDefaultResultStorageBlock
		? "loading"
		: hasConfiguredMissingBlock
			? "missing"
			: !defaultResultStorageBlockId
				? "empty"
				: undefined;

	return (
		<Card className="p-4">
			<div className="flex max-w-3xl flex-col gap-3">
				<div className="flex min-w-0 flex-col gap-3">
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
						<DefaultResultStorageStatus state={statusState} />
					)}
				</div>
				<div className="flex flex-col gap-2 sm:flex-row sm:items-center">
					<Select
						value={selectValue}
						onValueChange={onUpdateDefaultResultStorage}
						disabled={isMutating || storageBlockDocuments.length === 0}
					>
						<SelectTrigger
							className="w-full sm:w-64"
							aria-label="Default result storage block"
						>
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
	state: "empty" | "loading" | "missing" | undefined;
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

	if (state === "missing") {
		return (
			<div className="flex items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-muted-foreground">
				<div className="flex size-8 items-center justify-center rounded border border-destructive/30 bg-background">
					<Icon id="CircleAlert" className="size-4 text-destructive" />
				</div>
				<div>
					<div className="font-medium text-foreground">
						Configured block not found
					</div>
					<div>The configured default storage block could not be found.</div>
				</div>
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
