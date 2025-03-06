import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";

export const WorkPoolsPageHeader = () => (
	<div className="flex items-center justify-between">
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem className="text-xl font-semibold">
					Work Pools
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	</div>
);
