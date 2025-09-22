import type * as React from "react";
import { cn } from "@/utils";

type LayoutWellProps = {
	children: React.ReactNode;
	className?: string;
};

type LayoutWellHeaderProps = {
	children: React.ReactNode;
	className?: string;
};

type LayoutWellSidebarProps = {
	children: React.ReactNode;
	className?: string;
};

type LayoutWellContentProps = {
	children: React.ReactNode;
	className?: string;
};

export const LayoutWell = ({ children, className }: LayoutWellProps) => {
	return (
		<div className={cn("min-h-screen bg-background", className)}>
			<div className="w-full">
				<div className="flex flex-col lg:flex-row lg:gap-8">{children}</div>
			</div>
		</div>
	);
};

export const LayoutWellHeader = ({
	children,
	className,
}: LayoutWellHeaderProps) => {
	return <header className={cn("w-full", className)}>{children}</header>;
};

export const LayoutWellContent = ({
	children,
	className,
}: LayoutWellContentProps) => {
	return <div className={cn("flex-1 w-full", className)}>{children}</div>;
};

export const LayoutWellSidebar = ({
	children,
	className,
}: LayoutWellSidebarProps) => {
	return (
		<aside
			className={cn(
				"w-full lg:w-80 xl:w-96 lg:shrink-0",
				"lg:block hidden", // Hidden on mobile, shown on desktop
				className,
			)}
		>
			<div className="sticky top-8">{children}</div>
		</aside>
	);
};
