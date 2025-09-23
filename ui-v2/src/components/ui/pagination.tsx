import { DotsHorizontalIcon } from "@radix-ui/react-icons";
import { Link, type LinkProps } from "@tanstack/react-router";
import * as React from "react";
import {
	Button,
	type ButtonProps,
	buttonVariants,
} from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { cn } from "@/utils";

type PaginationProps = React.ComponentProps<"nav"> & {
	className?: string;
};

const Pagination = ({ className, ...props }: PaginationProps) => (
	<nav
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
	<PaginationLink
		aria-label="Go to previous page"
		size="default"
		className={cn("gap-1 pl-2.5", className)}
		{...props}
	>
		<Icon id="ChevronLeft" className="size-4" />
		<span>Previous</span>
	</PaginationLink>
);
PaginationPrevious.displayName = "PaginationPrevious";

const PaginationPreviousButton = ({
	className,
	...props
}: React.ComponentProps<typeof Button> & { className?: string }) => (
	<Button
		aria-label="Go to previous page"
		size="default"
		variant="ghost"
		className={cn("gap-1 pl-2.5", className)}
		{...props}
	>
		<Icon id="ChevronLeft" className="size-4" />
	</Button>
);
PaginationPreviousButton.displayName = "PaginationPreviousButton";

const PaginationNext = ({
	className,
	...props
}: React.ComponentProps<typeof PaginationLink> & LinkProps) => (
	<PaginationLink
		aria-label="Go to next page"
		size="default"
		className={cn("gap-1 pr-2.5", className)}
		{...props}
	>
		<span>Next</span>
		<Icon id="ChevronRight" className="size-4" />
	</PaginationLink>
);
PaginationNext.displayName = "PaginationNext";

const PaginationNextButton = ({
	className,
	...props
}: React.ComponentProps<typeof Button> & { className?: string }) => (
	<Button
		aria-label="Go to next page"
		variant="ghost"
		size="default"
		className={cn("gap-1 pr-2.5", className)}
		{...props}
	>
		<Icon id="ChevronRight" className="size-4" />
	</Button>
);
PaginationNextButton.displayName = "PaginationNextButton";

type PaginationEllipsisProps = React.ComponentProps<"span"> & {
	className?: string;
};

const PaginationEllipsis = ({
	className,
	...props
}: PaginationEllipsisProps) => (
	<span
		aria-hidden
		className={cn("flex size-9 items-center justify-center", className)}
		{...props}
	>
		<DotsHorizontalIcon className="size-4" />
		<span className="sr-only">More pages</span>
	</span>
);
PaginationEllipsis.displayName = "PaginationEllipsis";

const PaginationFirstButton = ({
	className,
	...props
}: React.ComponentProps<typeof Button> & { className?: string }) => (
	<Button
		aria-label="Go to first page"
		variant="ghost"
		size="default"
		className={cn("gap-1 pl-2.5", className)}
		{...props}
	>
		<Icon id="ChevronsLeft" className="size-4" />
	</Button>
);
PaginationFirstButton.displayName = "PaginationFirstButton";

const PaginationLastButton = ({
	className,
	...props
}: React.ComponentProps<typeof Button> & { className?: string }) => (
	<Button
		aria-label="Go to last page"
		variant="ghost"
		size="default"
		className={cn("gap-1 pr-2.5", className)}
		{...props}
	>
		<Icon id="ChevronsRight" className="size-4" />
	</Button>
);

export {
	Pagination,
	PaginationContent,
	PaginationLink,
	PaginationItem,
	PaginationPrevious,
	PaginationNext,
	PaginationEllipsis,
	PaginationPreviousButton,
	PaginationNextButton,
	PaginationFirstButton,
	PaginationLastButton,
};
