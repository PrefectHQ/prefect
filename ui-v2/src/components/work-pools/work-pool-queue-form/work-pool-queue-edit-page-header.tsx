import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

type WorkPoolQueueEditPageHeaderProps = {
	workPoolName: string;
	workQueueName: string;
};

export const WorkPoolQueueEditPageHeader = ({
	workPoolName,
	workQueueName,
}: WorkPoolQueueEditPageHeaderProps) => {
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

					<BreadcrumbItem className="min-w-0">
						<BreadcrumbLink
							to="/work-pools/work-pool/$workPoolName/queue/$workQueueName"
							params={{ workPoolName, workQueueName }}
							className="text-xl font-semibold truncate block"
							title={workQueueName}
						>
							{workQueueName}
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
