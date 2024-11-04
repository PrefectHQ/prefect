import {
	ChevronLeftIcon,
	ChevronRightIcon,
	DotsHorizontalIcon,
} from "@radix-ui/react-icons";
import * as React from "react";

import { ButtonProps, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Link, LinkProps } from "@tanstack/react-router";

type PaginationProps = React.ComponentProps<"nav"> & {
	className?: string;
};

const Pagination = ({ className, ...props }: PaginationProps) => (
	<nav
		role="navigation"
		aria-label="pagination"
		className={cn("mx-auto flex w-full justify-center", className)}
		{...props}
	/>
);
Pagination.displayName = "Pagination";

type PaginationContentProps = React.ComponentProps<"ul"> & {
	className?: string;
};

const PaginationContent = React.forwardRef<
	HTMLUListElement,
	PaginationContentProps
>(({ className, ...props }, ref) => (
	<ul
		ref={ref}
		className={cn("flex flex-row items-center gap-1", className)}
		{...props}
	/>
));
PaginationContent.displayName = "PaginationContent";

type PaginationItemProps = React.ComponentProps<"li"> & {
	className?: string;
};

const PaginationItem = React.forwardRef<HTMLLIElement, PaginationItemProps>(
	({ className, ...props }, ref) => (
		<li ref={ref} className={cn("", className)} {...props} />
	),
);
PaginationItem.displayName = "PaginationItem";

type PaginationLinkProps = {
	isActive?: boolean;
} & Pick<ButtonProps, "size"> &
	React.ComponentProps<"a">;

const PaginationLink = ({
	className,
	isActive,
	size = "icon",
	...props
}: PaginationLinkProps & LinkProps) => (
	<Link
		aria-current={isActive ? "page" : undefined}
		className={cn(
			buttonVariants({
				variant: isActive ? "outline" : "ghost",
				size,
			}),
			className,
		)}
		{...props}
	/>
);
PaginationLink.displayName = "PaginationLink";

const PaginationPrevious = ({
	className,
	...props
}: React.ComponentProps<typeof PaginationLink> & LinkProps) => (
	<Link
		aria-label="Go to previous page"
		className={cn(
			buttonVariants({
				variant: "ghost",
				size: "default",
			}),
			"gap-1 pl-2.5",
			className,
		)}
		{...props}
	>
		<ChevronLeftIcon className="h-4 w-4" />
		<span>Previous</span>
	</Link>
);
PaginationPrevious.displayName = "PaginationPrevious";

const PaginationNext = ({
	className,
	...props
}: React.ComponentProps<typeof PaginationLink> & LinkProps) => (
	<Link
		aria-label="Go to next page"
		className={cn(
			buttonVariants({
				variant: "ghost",
				size: "default",
			}),
			"gap-1 pr-2.5",
			className,
		)}
		{...props}
	>
		<span>Next</span>
		<ChevronRightIcon className="h-4 w-4" />
	</Link>
);
PaginationNext.displayName = "PaginationNext";

type PaginationEllipsisProps = React.ComponentProps<"span"> & {
	className?: string;
};

const PaginationEllipsis = ({
	className,
	...props
}: PaginationEllipsisProps) => (
	<span
		aria-hidden
		className={cn("flex h-9 w-9 items-center justify-center", className)}
		{...props}
	>
		<DotsHorizontalIcon className="h-4 w-4" />
		<span className="sr-only">More pages</span>
	</span>
);
PaginationEllipsis.displayName = "PaginationEllipsis";

export {
	Pagination,
	PaginationContent,
	PaginationLink,
	PaginationItem,
	PaginationPrevious,
	PaginationNext,
	PaginationEllipsis,
};
