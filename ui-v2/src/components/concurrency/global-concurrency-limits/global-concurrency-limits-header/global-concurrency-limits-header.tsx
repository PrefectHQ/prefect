import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";

type GlobalConcurrencyLimitsHeaderProps = {
	onAdd: () => void;
	canCreate?: boolean;
};

export const GlobalConcurrencyLimitsHeader = ({
	onAdd,
	canCreate = true,
}: GlobalConcurrencyLimitsHeaderProps) => {
	return (
		<div className="flex items-center gap-2">
			<Breadcrumb>
				<BreadcrumbList>
					<BreadcrumbItem className="text-xl font-semibold">
						Global Concurrency Limits
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
			{canCreate && (
				<Button
					onClick={onAdd}
					size="icon"
					className="size-7"
					variant="outline"
					aria-label="add global concurrency limit"
				>
					<Icon id="Plus" className="size-4" />
				</Button>
			)}
		</div>
	);
};
