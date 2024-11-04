import { ChevronRightIcon, DotsHorizontalIcon } from "@radix-ui/react-icons";
import { Slot } from "@radix-ui/react-slot";
import * as React from "react";

import { cn } from "@/lib/utils";

const Breadcrumb = React.forwardRef<
	HTMLElement,
	React.ComponentPropsWithoutRef<"nav"> & {
		separator?: React.ReactNode;
	}
>(({ ...props }, ref) => <nav ref={ref} aria-label="breadcrumb" {...props} />);
Breadcrumb.displayName = "Breadcrumb";

type BreadcrumbListProps = React.ComponentPropsWithoutRef<"ol"> & {
	className?: string;
};

const BreadcrumbList = React.forwardRef<HTMLOListElement, BreadcrumbListProps>(
	({ className, ...props }, ref) => (
		<ol
			ref={ref}
			className={cn(
				"flex flex-wrap items-center gap-1.5 break-words text-sm text-muted-foreground sm:gap-2.5",
				className,
			)}
			{...props}
		/>
	),
);
BreadcrumbList.displayName = "BreadcrumbList";

type BreadcrumbItemProps = React.ComponentPropsWithoutRef<"li"> & {
	className?: string;
};

const BreadcrumbItem = React.forwardRef<HTMLLIElement, BreadcrumbItemProps>(
	({ className, ...props }, ref) => (
		<li
			ref={ref}
			className={cn("inline-flex items-center gap-1.5", className)}
			{...props}
		/>
	),
);
BreadcrumbItem.displayName = "BreadcrumbItem";

type BreadcrumbLinkProps = React.ComponentPropsWithoutRef<"a"> & {
	asChild?: boolean;
	className?: string;
};

const BreadcrumbLink = React.forwardRef<HTMLAnchorElement, BreadcrumbLinkProps>(
	({ asChild, className, ...props }, ref) => {
		const Comp = asChild ? Slot : "a";

		return (
			<Comp
				ref={ref}
				className={cn("transition-colors hover:text-foreground", className)}
				{...props}
			/>
		);
	},
);
BreadcrumbLink.displayName = "BreadcrumbLink";

type BreadcrumbPageProps = React.ComponentPropsWithoutRef<"span"> & {
	className?: string;
};

const BreadcrumbPage = React.forwardRef<HTMLSpanElement, BreadcrumbPageProps>(
	({ className, ...props }, ref) => (
		<span
			ref={ref}
			role="link"
			aria-disabled="true"
			aria-current="page"
			className={cn("font-normal text-foreground", className)}
			{...props}
		/>
	),
);
BreadcrumbPage.displayName = "BreadcrumbPage";

type BreadcrumbSeparatorProps = React.ComponentPropsWithoutRef<"li"> & {
	className?: string;
};

const BreadcrumbSeparator = ({
	children,
	className,
	...props
}: BreadcrumbSeparatorProps) => (
	<li
		role="presentation"
		aria-hidden="true"
		className={cn("[&>svg]:size-3.5", className)}
		{...props}
	>
		{children ?? <ChevronRightIcon />}
	</li>
);
BreadcrumbSeparator.displayName = "BreadcrumbSeparator";

type BreadcrumbEllipsisProps = React.ComponentPropsWithoutRef<"span"> & {
	className?: string;
};

const BreadcrumbEllipsis = ({
	className,
	...props
}: BreadcrumbEllipsisProps) => (
	<span
		role="presentation"
		aria-hidden="true"
		className={cn("flex h-9 w-9 items-center justify-center", className)}
		{...props}
	>
		<DotsHorizontalIcon className="h-4 w-4" />
		<span className="sr-only">More</span>
	</span>
);
BreadcrumbEllipsis.displayName = "BreadcrumbElipssis";

export {
	Breadcrumb,
	BreadcrumbList,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbPage,
	BreadcrumbSeparator,
	BreadcrumbEllipsis,
};
