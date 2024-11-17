import { components } from "@/api/prefect";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { PlusIcon } from "lucide-react";
import { Link } from "@tanstack/react-router";


const WorkPoolsPage = ({ 
    workPools, 
    totalWorkPoolsCount,
    filteredWorkPoolsCount,
}: {
    workPools: components["schemas"]["WorkPool"][];
    totalWorkPoolsCount: number;
    filteredWorkPoolsCount: number;
}) => {
	return (
		<div className="flex flex-col gap-4 p-4">
			<div className="flex items-center gap-2">
				<Breadcrumb>
					<BreadcrumbList>
						<BreadcrumbItem className="text-xl font-semibold">
							Work Pools
						</BreadcrumbItem>
					</BreadcrumbList>
				</Breadcrumb>
				<Button
					size="icon"
					className="h-7 w-7"
					variant="outline"
					asChild
				>
					<Link to="/work-pools/create">
						<PlusIcon className="h-4 w-4" />
					</Link>
				</Button>
			</div>
			<pre className="whitespace-pre-wrap">
				{JSON.stringify([workPools, totalWorkPoolsCount, filteredWorkPoolsCount], null, 2)}
			</pre>
		</div>
	);
};

export default WorkPoolsPage;