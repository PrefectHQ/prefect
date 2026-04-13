import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

type WorkPoolQueueCreatePageHeaderProps = {
	workPoolName: string;
};

export const WorkPoolQueueCreatePageHeader = ({
	workPoolName,
}: WorkPoolQueueCreatePageHeaderProps) => {
	return (
		<header>
			<Breadcrumb className="min-w-0">
				<BreadcrumbList className="flex-nowrap">
					<BreadcrumbItem>
						<BreadcrumbLink to="/work-pools" className="text-xl font-semibold">
							Work Pools
						</BreadcrumbLink>
					</BreadcrumbItem>
					<BreadcrumbSeparator />

					<BreadcrumbItem className="min-w-0">
						<BreadcrumbLink
							to="/work-pools/work-pool/$workPoolName"
							params={{ workPoolName }}
							className="text-xl font-semibold truncate block"
							title={workPoolName}
						>
							{workPoolName}
						</BreadcrumbLink>
					</BreadcrumbItem>
					<BreadcrumbSeparator />

					<BreadcrumbItem className="text-xl font-semibold">
						<BreadcrumbPage>Create Work Queue</BreadcrumbPage>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
		</header>
	);
};
