import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

type BlockDocumentDetailsPageHeaderProps = {
	blockName: string;
};

export const BlockDocumentDetailsPageHeader = ({
	blockName,
}: BlockDocumentDetailsPageHeaderProps) => {
	return (
		<Breadcrumb className="min-w-0">
			<BreadcrumbList className="flex-nowrap">
				<BreadcrumbItem>
					<BreadcrumbLink to="/blocks" className="text-xl font-semibold">
						Blocks
					</BreadcrumbLink>
				</BreadcrumbItem>
				<BreadcrumbSeparator />

				<BreadcrumbItem className="text-xl font-semibold min-w-0">
					<span className="truncate block" title={blockName}>
						{blockName}
					</span>
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	);
};
