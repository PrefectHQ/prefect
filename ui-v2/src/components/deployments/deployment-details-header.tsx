import type { Deployment } from "@/api/deployments";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "../ui/breadcrumb";

type DeploymentDetailsHeaderProps = {
	deployment: Deployment;
};
export const DeploymentDetailsHeader = ({
	deployment,
}: DeploymentDetailsHeaderProps) => {
	return (
		<Breadcrumb className="min-w-0">
			<BreadcrumbList className="flex-nowrap">
				<BreadcrumbItem>
					<BreadcrumbLink to="/deployments" className="text-xl font-semibold">
						Deployments
					</BreadcrumbLink>
				</BreadcrumbItem>
				<BreadcrumbSeparator />
				<BreadcrumbItem className="text-xl font-semibold min-w-0">
					<BreadcrumbPage className="truncate block" title={deployment.name}>
						{deployment.name}
					</BreadcrumbPage>
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	);
};
