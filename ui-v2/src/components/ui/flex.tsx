import { cn } from "@/lib/utils";
import { createElement, forwardRef } from "react";
import { UtilityProps, spacingUtiltiesClasses } from "./utils/spacing-utils";

type Props = Omit<UtilityProps, "display"> & {
	className?: string;
	children: React.ReactNode;
};

export const Flex = forwardRef<HTMLDivElement, Props>(
	({ className, ...props }, ref) => {
		return createElement("div", {
			className: cn("flex", spacingUtiltiesClasses(props), className),
			ref,
			...props,
		});
	},
);

Flex.displayName = "Flex";
