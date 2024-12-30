import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

type Props = {
	tag: string;
};

export const NavHeader = ({ tag }: Props) => {
	return (
		<div className="flex items-center gap-2">
			<Breadcrumb>
				<BreadcrumbList>
					<BreadcrumbLink
						to="/concurrency-limits"
						className="text-xl font-semibold"
					>
						Concurrency Limits
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
