import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Suspense } from "react";
import { buildFLowDetailsQuery } from "@/api/flows";
import { Icon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";

type FlowLinkProps = {
	flowId: string;
};

export const FlowLink = ({ flowId }: FlowLinkProps) => {
	return (
		<Suspense fallback={<Skeleton className="h-4 w-full" />}>
			<FlowLinkImplementation flowId={flowId} />
		</Suspense>
	);
};

const FlowLinkImplementation = ({ flowId }: FlowLinkProps) => {
	const { data: flow } = useSuspenseQuery(buildFLowDetailsQuery(flowId));

	return (
		<div className="flex items-center gap-1 text-xs">
			Flow
			<Link
				to="/flows/flow/$id"
				params={{ id: flow.id }}
				className="flex items-center gap-1"
			>
				<Icon id="Workflow" className="size-4" />
				{flow.name}
			</Link>
		</div>
	);
};
