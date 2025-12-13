import * as CollapsiblePrimitive from "@radix-ui/react-collapsible";
import type * as React from "react";

function Collapsible({
	...props
}: React.ComponentProps<typeof CollapsiblePrimitive.Root>) {
	return <CollapsiblePrimitive.Root data-slot="collapsible" {...props} />;
}

function CollapsibleTrigger({
	...props
}: React.ComponentProps<typeof CollapsiblePrimitive.Trigger>) {
	return (
		<CollapsiblePrimitive.Trigger data-slot="collapsible-trigger" {...props} />
	);
}

function CollapsibleContent({
	...props
}: React.ComponentProps<typeof CollapsiblePrimitive.Content>) {
	return (
		<CollapsiblePrimitive.Content data-slot="collapsible-content" {...props} />
	);
}

export { Collapsible, CollapsibleTrigger, CollapsibleContent };
