import type { BlockDocument } from "@/api/block-documents";

type BlockDocumentEditPageProps = {
	blockDocument: BlockDocument;
};

export const BlockDocumentEditPage = ({
	blockDocument,
}: BlockDocumentEditPageProps) => {
	// TODO
	return JSON.stringify(blockDocument);
};
