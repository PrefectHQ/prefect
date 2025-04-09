import type { Deployment } from "@/api/deployments";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

type DeploymentActionHeaderProps = {
	deployment: Deployment;
	action: "Edit" | "Duplicate" | "Run";
};

export const DeploymentActionHeader = ({
	deployment,
	action,
}: DeploymentActionHeaderProps) => {
	return (
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem>
					<BreadcrumbLink to="/deployments" className="text-xl font-semibold">
						Deployments
					</BreadcrumbLink>
				</BreadcrumbItem>
				<BreadcrumbSeparator />

				<BreadcrumbItem>
					<BreadcrumbLink
						to="/deployments/deployment/$id"
						params={{ id: deployment.id }}
						className="text-xl font-semibold"
					>
						{deployment.name}
					</BreadcrumbLink>
				</BreadcrumbItem>
				<BreadcrumbSeparator />

				<BreadcrumbItem className="text-xl font-semibold">
					<BreadcrumbPage>{action}</BreadcrumbPage>
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	);
};
