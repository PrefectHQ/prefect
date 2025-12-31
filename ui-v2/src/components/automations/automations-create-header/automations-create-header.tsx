import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { DocsLink } from "@/components/ui/docs-link";

type BreadcrumbConfig = {
	label: string;
	href?: string;
};

type AutomationsCreateHeaderProps = {
	title?: string;
	breadcrumbs?: BreadcrumbConfig[];
};

const DEFAULT_BREADCRUMBS: BreadcrumbConfig[] = [
	{ label: "Automations", href: "/automations" },
	{ label: "Create" },
];

export const AutomationsCreateHeader = ({
	breadcrumbs = DEFAULT_BREADCRUMBS,
}: AutomationsCreateHeaderProps) => (
	<div className="flex items-center justify-between">
		<NavHeader breadcrumbs={breadcrumbs} />
		<DocsLink label="Documentation" id="automations-guide" />
	</div>
);

type NavHeaderProps = {
	breadcrumbs: BreadcrumbConfig[];
};

const NavHeader = ({ breadcrumbs }: NavHeaderProps) => (
	<div className="flex items-center gap-2">
		<Breadcrumb>
			<BreadcrumbList>
				{breadcrumbs.map((crumb, index) => {
					const isLast = index === breadcrumbs.length - 1;
					return (
						<span key={crumb.label} className="contents">
							<BreadcrumbItem className="text-xl font-semibold">
								{crumb.href ? (
									<BreadcrumbLink to={crumb.href}>{crumb.label}</BreadcrumbLink>
								) : (
									<BreadcrumbPage>{crumb.label}</BreadcrumbPage>
								)}
							</BreadcrumbItem>
							{!isLast && <BreadcrumbSeparator />}
						</span>
					);
				})}
			</BreadcrumbList>
		</Breadcrumb>
	</div>
);
