import { useState } from "react";
import { BlockDocumentCombobox } from "@/components/blocks/block-document-combobox";
import { BlockDocumentCreateDialog } from "@/components/blocks/block-document-create-dialog";

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
	const [createDialogOpen, setCreateDialogOpen] = useState(false);

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
		<div id={id}>
			<BlockDocumentCombobox
				blockTypeSlug={blockTypeSlug}
				selectedBlockDocumentId={selectedBlockDocumentId}
				onSelect={handleSelect}
				onCreateNew={() => setCreateDialogOpen(true)}
			/>
			<BlockDocumentCreateDialog
				open={createDialogOpen}
				onOpenChange={setCreateDialogOpen}
				blockTypeSlug={blockTypeSlug}
				onCreated={handleCreated}
			/>
		</div>
	);
}
