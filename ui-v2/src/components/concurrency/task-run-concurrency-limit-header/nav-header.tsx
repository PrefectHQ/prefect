import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Link } from "@tanstack/react-router";

type Props = {
	tag: string;
};

export const NavHeader = ({ tag }: Props) => {
	return (
		<div className="flex items-center gap-2">
			<Breadcrumb>
				<BreadcrumbList>
					<BreadcrumbLink asChild className="text-xl font-semibold">
						<Link to="/concurrency-limits">Concurrency Limits </Link>
					</BreadcrumbLink>
					<BreadcrumbSeparator />
					<BreadcrumbItem className="text-xl font-semibold">
						<BreadcrumbPage>{tag}</BreadcrumbPage>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
		</div>
	);
};
