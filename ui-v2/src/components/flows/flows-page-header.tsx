import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";

export const FlowsHeader = () => {
	return (
		<div className="flex items-center mb-4">
			<Header />
		</div>
	);
};

const Header = () => (
	<div className="flex items-center ">
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem className="text-xl font-bold text-foreground">
					Flows
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	</div>
);
