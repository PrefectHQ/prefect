import type { WorkPool } from "@/api/work-pools";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

type WorkPoolEditPageHeaderProps = {
	workPool: WorkPool;
};

export const WorkPoolEditPageHeader = ({
	workPool,
}: WorkPoolEditPageHeaderProps) => {
	return (
		<header className="mb-6">
			<Breadcrumb>
				<BreadcrumbList>
					<BreadcrumbItem>
						<BreadcrumbLink to="/work-pools" className="text-xl font-semibold">
							Work Pools
						</BreadcrumbLink>
					</BreadcrumbItem>
					<BreadcrumbSeparator />

					<BreadcrumbItem>
						<BreadcrumbLink
							to="/work-pools/work-pool/$workPoolName"
							params={{ workPoolName: workPool.name }}
							className="text-xl font-semibold"
						>
							{workPool.name}
						</BreadcrumbLink>
					</BreadcrumbItem>
					<BreadcrumbSeparator />

					<BreadcrumbItem className="text-xl font-semibold">
						<BreadcrumbPage>Edit</BreadcrumbPage>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
		</header>
	);
};
