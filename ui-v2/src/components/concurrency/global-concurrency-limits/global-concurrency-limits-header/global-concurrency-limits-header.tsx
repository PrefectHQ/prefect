import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";

type GlobalConcurrencyLimitsHeaderProps = {
	onAdd: () => void;
};

export const GlobalConcurrencyLimitsHeader = ({
	onAdd,
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
			<Button
				onClick={onAdd}
				size="icon"
				className="size-7"
				variant="outline"
				aria-label="add global concurrency limit"
			>
				<Icon id="Plus" className="size-4" />
			</Button>
		</div>
	);
};
