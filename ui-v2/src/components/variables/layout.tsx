import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";

export const VariablesLayout = ({
	onAddVariableClick,
	children,
}: {
	onAddVariableClick: () => void;
	children: React.ReactNode;
}) => {
	return (
		<div className="flex flex-col gap-4 p-4">
			<div className="flex items-center gap-2">
				<Breadcrumb>
					<BreadcrumbList>
						<BreadcrumbItem className="text-xl font-semibold">
							Variables
						</BreadcrumbItem>
					</BreadcrumbList>
				</Breadcrumb>
				<Button
					size="icon"
					className="h-7 w-7"
					variant="outline"
					onClick={() => onAddVariableClick()}
				>
					<Icon id="Plus" className="h-4 w-4" />
				</Button>
			</div>
			{children}
		</div>
	);
};
