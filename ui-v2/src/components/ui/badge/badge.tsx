import { Slot } from "@radix-ui/react-slot";
import type { VariantProps } from "class-variance-authority";
import type * as React from "react";
import { badgeVariants } from "./styles";

import { cn } from "@/lib/utils";

export type BadgeProps = React.ComponentProps<"span"> &
	VariantProps<typeof badgeVariants> & { asChild?: boolean };

function Badge({ className, variant, asChild = false, ...props }: BadgeProps) {
	const Comp = asChild ? Slot : "span";

	return (
		<Comp
			data-slot="badge"
			className={cn(badgeVariants({ variant }), className)}
			{...props}
		/>
	);
}

export { Badge };
