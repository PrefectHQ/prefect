import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { DocsLink } from "@/components/ui/docs-link";

export const FlowsHeader = () => {
	return (
		<div className="flex items-center justify-between mb-4">
			<Header />
			<DocsLink id="flows-guide" label="Documentation" />
		</div>
	);
};

const Header = () => (
	<div className="flex items-center ">
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem className="text-xl font-bold text-black">
					Flows
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	</div>
);
