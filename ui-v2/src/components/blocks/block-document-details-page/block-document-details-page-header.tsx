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
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem>
					<BreadcrumbLink to="/blocks" className="text-xl font-semibold">
						Blocks
					</BreadcrumbLink>
				</BreadcrumbItem>
				<BreadcrumbSeparator />

				<BreadcrumbItem className="text-xl font-semibold">
					{blockName}
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	);
};
