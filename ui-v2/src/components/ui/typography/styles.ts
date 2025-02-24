import { cva } from "class-variance-authority";

export const typographyVariants = cva("", {
	variants: {
		variant: {
			h1: "text-4xl font-extrabold tracking-tigh",
			h2: "text-3xl font-semibold tracking-tight",
			h3: "text-2xl font-semibold tracking-tight",
			h4: "text-xl font-semibold tracking-tight",
			bodyLarge: "text-lg",
			body: "text-base",
			bodySmall: "text-sm",
			xsmall: "text-xs",
		},
	},
	defaultVariants: {
		variant: "body",
	},
});
