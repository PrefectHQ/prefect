import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import type { FlowRunsDataTableRow } from "./data-table";

type NameCellProps = {
	flowRun: FlowRunsDataTableRow;
};

export const NameCell = ({ flowRun }: NameCellProps) => {
	return (
		<div className="flex items-center">
			<Breadcrumb>
				<BreadcrumbList>
					<BreadcrumbItem>
						<BreadcrumbLink
							to="/flows/flow/$id"
							params={{ id: flowRun.flow_id }}
						>
							{flowRun.flow.name}
						</BreadcrumbLink>
					</BreadcrumbItem>

					<BreadcrumbSeparator>/</BreadcrumbSeparator>

					<BreadcrumbItem className="font-bold text-black">
						<BreadcrumbLink to="/runs/flow-run/$id" params={{ id: flowRun.id }}>
							{flowRun.name}
						</BreadcrumbLink>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
		</div>
	);
};
