import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";

export const DeploymentsLayout = ({
	children,
}: {
	children: React.ReactNode;
}) => {
	return (
		<div className="flex flex-col gap-4 p-4">
			<div className="flex items-center gap-2">
				<Breadcrumb>
					<BreadcrumbList>
						<BreadcrumbItem className="text-xl font-semibold">
							Deployments
						</BreadcrumbItem>
					</BreadcrumbList>
				</Breadcrumb>
			</div>
			{children}
		</div>
	);
};
