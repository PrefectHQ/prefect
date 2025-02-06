import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { DocsLink } from "@/components/ui/docs-link";

export const ArtifactsHeader = () => {
	return (
		<div className="flex items-center justify-between">
			<Header />
			<DocsLink id="artifacts-guide" label="Documentation" />
		</div>
	);
};

const Header = () => (
	<div className="flex items-center gap-2">
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem className="text-xl font-semibold">
					Artifacts
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	</div>
);
