import type React from "react";
import { cn } from "@/lib/utils";

interface PageHeadingProps {
	breadcrumbs?: React.ReactNode;
	title: React.ReactNode;
	subtitle?: React.ReactNode;
	actions?: React.ReactNode;
	className?: string;
}

export const PageHeading = ({
	breadcrumbs,
	title,
	subtitle,
	actions,
	className,
}: PageHeadingProps) => {
	return (
		<header
			className={cn(
				"flex flex-col space-y-4 md:flex-row md:items-center md:justify-between md:space-y-0",
				className,
			)}
		>
			<div className="flex flex-col space-y-2">
				{breadcrumbs && <nav>{breadcrumbs}</nav>}
				<div className="flex flex-col space-y-1">
					<h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
					{subtitle && (
						<p className="text-sm text-muted-foreground">{subtitle}</p>
					)}
				</div>
			</div>
			{actions && <div className="flex items-center space-x-2">{actions}</div>}
		</header>
	);
};
