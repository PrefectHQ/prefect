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
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem>
					<BreadcrumbLink to="/deployments" className="text-xl font-semibold">
						Deployments
					</BreadcrumbLink>
				</BreadcrumbItem>
				<BreadcrumbSeparator />
				<BreadcrumbItem className="text-xl font-semibold">
					<BreadcrumbPage>{deployment.name}</BreadcrumbPage>
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	);
};
