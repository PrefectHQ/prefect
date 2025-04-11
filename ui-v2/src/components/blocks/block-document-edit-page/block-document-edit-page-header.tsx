import type { BlockDocument } from "@/api/block-documents";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

type BlockDocumentEditPageHeaderProps = {
	blockDocument: BlockDocument;
};

export const BlockDocumentEditPageHeader = ({
	blockDocument,
}: BlockDocumentEditPageHeaderProps) => {
	return (
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem>
					<BreadcrumbLink to="/blocks" className="text-xl font-semibold">
						Blocks
					</BreadcrumbLink>
				</BreadcrumbItem>
				<BreadcrumbSeparator />

				<BreadcrumbItem>
					<BreadcrumbLink
						to="/blocks/block/$id"
						params={{ id: blockDocument.id }}
						className="text-xl font-semibold"
					>
						{blockDocument.name ??
							blockDocument.block_type_name ??
							blockDocument.id}
					</BreadcrumbLink>
				</BreadcrumbItem>
				<BreadcrumbSeparator />

				<BreadcrumbItem className="text-xl font-semibold">
					<BreadcrumbPage>Edit</BreadcrumbPage>
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	);
};
