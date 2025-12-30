import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Suspense } from "react";
import { buildFLowDetailsQuery } from "@/api/flows";
import { Icon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";

type FlowIconTextProps = {
	flowId: string;
};

export const FlowIconText = ({ flowId }: FlowIconTextProps) => {
	return (
		<Suspense fallback={<Skeleton className="h-4 w-full" />}>
			<FlowIconTextImplementation flowId={flowId} />
		</Suspense>
	);
};

const FlowIconTextImplementation = ({ flowId }: FlowIconTextProps) => {
	const { data: flow } = useSuspenseQuery(buildFLowDetailsQuery(flowId));

	return (
		<Link
			to="/flows/flow/$id"
			params={{ id: flow.id }}
			className="flex items-center gap-1"
		>
			<Icon id="Workflow" className="size-4" />
			{flow.name}
		</Link>
	);
};
