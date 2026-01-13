import { Suspense, useState } from "react";
import { BlockDocumentCombobox } from "@/components/blocks/block-document-combobox";
import { BlockDocumentCreateDialog } from "@/components/blocks/block-document-create-dialog";

type BlockDocumentReferenceValue = {
	$ref: string;
};

type SchemaFormInputBlockDocumentProps = {
	value: BlockDocumentReferenceValue | undefined;
	onValueChange: (value: BlockDocumentReferenceValue | undefined) => void;
	blockTypeSlug: string;
	id: string;
};

export function SchemaFormInputBlockDocument({
	value,
	onValueChange,
	blockTypeSlug,
	id,
}: SchemaFormInputBlockDocumentProps) {
	const [createDialogOpen, setCreateDialogOpen] = useState(false);

	const handleSelect = (blockDocumentId: string | undefined) => {
		if (!blockDocumentId) {
			onValueChange(undefined);
			return;
		}
		onValueChange({ $ref: blockDocumentId });
	};

	const handleBlockCreated = (blockDocumentId: string) => {
		onValueChange({ $ref: blockDocumentId });
		setCreateDialogOpen(false);
	};

	return (
		<div id={id}>
			<Suspense
				fallback={<div className="h-10 animate-pulse bg-muted rounded" />}
			>
				<BlockDocumentCombobox
					blockTypeSlug={blockTypeSlug}
					selectedBlockDocumentId={value?.$ref}
					onSelect={handleSelect}
					onCreateNew={() => setCreateDialogOpen(true)}
				/>
			</Suspense>
			<BlockDocumentCreateDialog
				open={createDialogOpen}
				onOpenChange={setCreateDialogOpen}
				blockTypeSlug={blockTypeSlug}
				onCreated={handleBlockCreated}
			/>
		</div>
	);
}
