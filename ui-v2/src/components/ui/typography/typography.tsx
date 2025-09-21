import { createElement, type Ref } from "react";
import { cn } from "@/utils";

import { typographyVariants } from "./styles";

const VARIANTS_TO_ELEMENT_MAP = {
	h1: "h1",
	h2: "h2",
	h3: "h3",
	h4: "h4",
	bodyLarge: "p",
	body: "p",
	bodySmall: "p",
	xsmall: "p",
} as const;

type Variant =
	| "h1"
	| "h2"
	| "h3"
	| "h4"
	| "bodyLarge"
	| "body"
	| "bodySmall"
	| "xsmall";
type FontFamily = "sans" | "serif" | "mono";

type TypographyProps = {
	className?: string;
	variant?: Variant;
	fontFamily?: FontFamily;
	children: React.ReactNode;
	ref?: Ref<HTMLElement>;
};

export function Typography({
	className,
	variant = "body",
	fontFamily = "sans",
	ref,
	...props
}: TypographyProps) {
	return createElement(VARIANTS_TO_ELEMENT_MAP[variant], {
		className: cn(
			typographyVariants({
				variant,
				className: cn({
					"font-sans": fontFamily === "sans",
					"font-serif": fontFamily === "serif",
					"font-mono": fontFamily === "mono",
				}),
			}),
			className,
		),
		ref,
		...props,
	});
}

Typography.displayName = "Typography";
