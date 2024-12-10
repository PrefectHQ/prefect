import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";

export const DeploymentsPageHeader = () => {
	return (
		<div className="flex items-center gap-2">
			<Breadcrumb>
				<BreadcrumbList>
					<BreadcrumbItem className="text-xl font-semibold">
						Deployments
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
		</div>
	);
};
