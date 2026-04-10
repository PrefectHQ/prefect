import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";

type TaskRunConcurrencyLimitsHeaderProps = {
	onAdd: () => void;
	canCreate?: boolean;
};

export const TaskRunConcurrencyLimitsHeader = ({
	onAdd,
	canCreate = true,
}: TaskRunConcurrencyLimitsHeaderProps) => {
	return (
		<div className="flex items-center gap-2">
			<Breadcrumb>
				<BreadcrumbList>
					<BreadcrumbItem className="text-xl font-semibold">
						Task Run Concurrency Limits
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
			{canCreate && (
				<Button
					onClick={onAdd}
					size="icon"
					className="size-7"
					variant="outline"
					aria-label="add task run concurrency limit"
				>
					<Icon id="Plus" className="size-4" />
				</Button>
			)}
		</div>
	);
};
