import type { BlockDocument } from "@/api/block-documents";
import { BlockDocumentActionMenu } from "@/components/blocks/block-document-action-menu";
import { BlockTypeDetails } from "@/components/blocks/block-type-details";
import { Card } from "@/components/ui/card";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { DOCS_LINKS } from "@/components/ui/docs-link";
import { PythonBlockSnippet } from "../python-example-snippet";
import { useDeleteBlockDocumentConfirmationDialog } from "../use-delete-block-document-confirmation-dialog";
import { BlockDocumentDetailsPageHeader } from "./block-document-details-page-header";
import { BlockDocumentSchemaProperties } from "./block-document-schema-properties";

type BlockDocumentDetailsPageProps = {
	blockDocument: BlockDocument;
};

export const BlockDocumentDetailsPage = ({
	blockDocument,
}: BlockDocumentDetailsPageProps) => {
	const [dialogState, handleConfirmDelete] =
		useDeleteBlockDocumentConfirmationDialog();

	const handleDeleteBlock = () =>
		handleConfirmDelete(blockDocument, { shouldNavigate: true });

	const { block_type } = blockDocument;

	const blockName =
		blockDocument.name ?? blockDocument.block_type_name ?? "Block Document";

	return (
		<>
			<div className="flex flex-col gap-4">
				<div className="flex items-center justify-between">
					<BlockDocumentDetailsPageHeader blockName={blockName} />
					<BlockDocumentActionMenu
						blockDocument={blockDocument}
						onDelete={handleDeleteBlock}
					/>
				</div>
				<Card className="p-4">
					<div className="grid grid-cols-[minmax(0,_1fr)_250px] gap-4 ">
						<div className="flex flex-col gap-4">
							{(block_type?.code_example || block_type?.documentation_url) && (
								<NeedHelpDocsLink
									hasCodeExample={Boolean(block_type?.code_example)}
									hasDocumentationUrl={Boolean(block_type?.documentation_url)}
								/>
							)}
							{block_type?.code_example && (
								<PythonBlockSnippet
									codeExample={block_type.code_example}
									name={blockDocument.name}
								/>
							)}
							{blockDocument.data && blockDocument.block_schema?.fields && (
								<BlockDocumentSchemaProperties
									data={blockDocument.data}
									fields={blockDocument.block_schema?.fields}
								/>
							)}
						</div>
						{block_type && <BlockTypeDetails blockType={block_type} />}
					</div>
				</Card>
			</div>
			<DeleteConfirmationDialog {...dialogState} />
		</>
	);
};

type NeedHelpDocsLinkProps = {
	hasCodeExample: boolean;
	hasDocumentationUrl: boolean;
};
function NeedHelpDocsLink({
	hasCodeExample,
	hasDocumentationUrl,
}: NeedHelpDocsLinkProps) {
	return (
		<div className="flex items-center gap-1">
			{hasCodeExample && (
				<p className="text-sm muted">
					Paste this snippet{" "}
					<span className="font-semibold">into your flows</span> to use this
					block.
				</p>
			)}
			{hasDocumentationUrl && (
				<p className="text-sm muted">
					Need help?{" "}
					<a
						className="underline text-link hover:text-link-hover visited:text-link"
						href={DOCS_LINKS["blocks-guide"]}
					>
						View Docs
					</a>
				</p>
			)}
		</div>
	);
}
