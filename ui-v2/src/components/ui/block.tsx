import { cn } from "@/lib/utils";
import { createElement, forwardRef } from "react";
import { UtilityProps, spacingUtiltiesClasses } from "./utils/spacing-utils";

type Props = Omit<
	UtilityProps,
	| "alignItems"
	| "alignSelf"
	| "display"
	| "flexDirection"
	| "gap"
	| "justifyContent"
	| "justifyItems"
	| "justifySelf"
> & {
	className?: string;
	children: React.ReactNode;
};

export const Block = forwardRef<HTMLDivElement, Props>(
	({ className, ...props }, ref) => {
		return createElement("div", {
			className: cn("block", spacingUtiltiesClasses(props), className),
			ref,
			...props,
		});
	},
);

Block.displayName = "Block";
