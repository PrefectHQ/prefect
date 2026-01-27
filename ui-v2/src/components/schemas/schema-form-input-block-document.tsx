import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense, useState } from "react";
import { buildCountFilterBlockDocumentsQuery } from "@/api/block-documents";
import { buildGetBlockTypeQuery } from "@/api/block-types";
import { BlockTypeLogo } from "@/components/block-type-logo/block-type-logo";
import { BlockDocumentCombobox } from "@/components/blocks/block-document-combobox";
import { BlockDocumentCreateDialog } from "@/components/blocks/block-document-create-dialog";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";

type BlockDocumentReferenceValue =
	| {
			$ref: string;
	  }
	| undefined;

type SchemaFormInputBlockDocumentProps = {
	value: BlockDocumentReferenceValue;
	onValueChange: (value: BlockDocumentReferenceValue) => void;
	blockTypeSlug: string;
	id: string;
};

export function SchemaFormInputBlockDocument({
	value,
	onValueChange,
	blockTypeSlug,
	id,
}: SchemaFormInputBlockDocumentProps) {
	return (
		<Suspense fallback={<SchemaFormInputBlockDocumentSkeleton />}>
			<SchemaFormInputBlockDocumentContent
				value={value}
				onValueChange={onValueChange}
				blockTypeSlug={blockTypeSlug}
				id={id}
			/>
		</Suspense>
	);
}

function SchemaFormInputBlockDocumentSkeleton() {
	return (
		<div className="flex items-center gap-2">
			<Skeleton className="size-8 rounded" />
			<Skeleton className="h-9 flex-1" />
			<Skeleton className="h-9 w-20" />
		</div>
	);
}

function SchemaFormInputBlockDocumentContent({
	value,
	onValueChange,
	blockTypeSlug,
	id,
}: SchemaFormInputBlockDocumentProps) {
	const [createDialogOpen, setCreateDialogOpen] = useState(false);

	const { data: blockType } = useSuspenseQuery(
		buildGetBlockTypeQuery(blockTypeSlug),
	);

	const { data: blockDocumentCount } = useSuspenseQuery(
		buildCountFilterBlockDocumentsQuery({
			block_types: {
				slug: { any_: [blockTypeSlug] },
			},
			block_documents: {
				operator: "and_",
				is_anonymous: { eq_: false },
			},
			include_secrets: false,
			sort: "BLOCK_TYPE_AND_NAME_ASC",
			offset: 0,
		}),
	);

	const hasBlockDocuments = blockDocumentCount > 0;
	const selectedBlockDocumentId = value?.$ref;

	const handleSelect = (blockDocumentId: string | undefined) => {
		if (blockDocumentId) {
			onValueChange({ $ref: blockDocumentId });
		} else {
			onValueChange(undefined);
		}
	};

	const handleCreated = (blockDocumentId: string) => {
		onValueChange({ $ref: blockDocumentId });
	};

	return (
		<div id={id} className="flex items-center gap-2">
			<BlockTypeLogo logoUrl={blockType.logo_url} alt={blockType.name} />
			{hasBlockDocuments && (
				<div className="flex-1">
					<BlockDocumentCombobox
						blockTypeSlug={blockTypeSlug}
						selectedBlockDocumentId={selectedBlockDocumentId}
						onSelect={handleSelect}
						onCreateNew={() => setCreateDialogOpen(true)}
					/>
				</div>
			)}
			<Button
				type="button"
				variant="outline"
				onClick={() => setCreateDialogOpen(true)}
			>
				<Icon id="Plus" className="mr-2 size-4" />
				Add
			</Button>
			<BlockDocumentCreateDialog
				open={createDialogOpen}
				onOpenChange={setCreateDialogOpen}
				blockTypeSlug={blockTypeSlug}
				onCreated={handleCreated}
			/>
		</div>
	);
}
