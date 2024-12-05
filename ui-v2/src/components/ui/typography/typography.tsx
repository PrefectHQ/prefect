import { cn } from "@/lib/utils";
import { createElement, forwardRef } from "react";

import { typographyVariants } from "./styles";

const VARIANTS_TO_ELEMENT_MAP = {
	h1: "h1",
	h2: "h2",
	h3: "h3",
	h4: "h4",
	bodyLarge: "p",
	body: "p",
	bodySmall: "p",
} as const;

type Variant = "h1" | "h2" | "h3" | "h4" | "bodyLarge" | "body" | "bodySmall";

type Props = {
	className?: string;
	variant?: Variant;
	children: React.ReactNode;
};

export const Typography = forwardRef<HTMLDivElement, Props>(
	({ className, variant = "body", ...props }, ref) => {
		return createElement(VARIANTS_TO_ELEMENT_MAP[variant], {
			className: cn(typographyVariants({ variant }), className),
			ref,
			...props,
		});
	},
);

Typography.displayName = "Typography";
