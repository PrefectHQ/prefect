import type { VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";
import { badgeVariants } from "./styles";
import React from "react";

export interface BadgeProps
	extends React.HTMLAttributes<HTMLDivElement>,
		VariantProps<typeof badgeVariants> {}

export const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
	({ className, variant, ...props }, ref) => (
		<div
			ref={ref}
			className={cn(badgeVariants({ variant }), className)}
			{...props}
		/>
	),
);

Badge.displayName = "Badge";
