import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";

type VariablesPageHeaderProps = {
	onAddVariableClick?: () => void;
};

export const VariablesPageHeader = ({
	onAddVariableClick,
}: VariablesPageHeaderProps) => {
	return (
		<div className="flex items-center gap-2">
			<Breadcrumb>
				<BreadcrumbList>
					<BreadcrumbItem className="text-xl font-semibold">
						Variables
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
			{onAddVariableClick && (
				<Button
					size="icon"
					className="size-7"
					variant="outline"
					aria-label="Add variable"
					onClick={() => onAddVariableClick()}
				>
					<Icon id="Plus" className="size-4" />
				</Button>
			)}
		</div>
	);
};
