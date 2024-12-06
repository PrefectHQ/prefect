import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Flex } from "@/components/ui/flex";
import { Icon } from "@/components/ui/icons";

export const VariablesLayout = ({
	onAddVariableClick,
	children,
}: {
	onAddVariableClick: () => void;
	children: React.ReactNode;
}) => {
	return (
		<Flex flexDirection="column" gap={4}>
			<Flex alignItems="center" gap={2}>
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
			</Flex>
			{children}
		</Flex>
	);
};
