import { buildGetTaskRunDetailsQuery } from "@/api/task-runs";
import { useSuspenseQuery } from "@tanstack/react-query";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "../ui/breadcrumb";

type TaskRunDetailsPageProps = {
	id: string;
	tab: "Logs" | "Artifacts" | "TaskInputs";
};

export const TaskRunDetailsPage = ({ id }: TaskRunDetailsPageProps) => {
	const { data: taskRun } = useSuspenseQuery(buildGetTaskRunDetailsQuery(id));

	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-col gap-2">
				<Breadcrumb>
					<BreadcrumbList>
						<BreadcrumbItem>
							<BreadcrumbLink to="/runs" className="text-xl font-semibold">
								Runs
							</BreadcrumbLink>
						</BreadcrumbItem>
						<BreadcrumbSeparator />
						{taskRun.flow_run_id && (
							<>
								<BreadcrumbItem>
									<BreadcrumbLink
										to="/runs/flow-run/$id"
										params={{ id: taskRun.flow_run_id }}
										className="text-xl font-semibold"
									>
										{taskRun.flow_run_id}
									</BreadcrumbLink>
								</BreadcrumbItem>
								<BreadcrumbSeparator />
							</>
						)}
						<BreadcrumbItem className="text-xl font-semibold">
							<BreadcrumbPage>{taskRun.name}</BreadcrumbPage>
						</BreadcrumbItem>
					</BreadcrumbList>
				</Breadcrumb>
			</div>
		</div>
	);
};
