import { useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Suspense } from "react";
import { buildFLowDetailsQuery, type Flow } from "@/api/flows";
import { Icon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";

type FlowIconTextBaseProps = {
	className?: string;
	iconSize?: number;
	onClick?: (e: React.MouseEvent<HTMLAnchorElement>) => void;
};

type FlowIconTextWithIdProps = FlowIconTextBaseProps & {
	flowId: string;
	flow?: never;
};

type FlowIconTextWithFlowProps = FlowIconTextBaseProps & {
	flow: Flow;
	flowId?: never;
};

type FlowIconTextProps = FlowIconTextWithIdProps | FlowIconTextWithFlowProps;

export const FlowIconText = (props: FlowIconTextProps) => {
	if ("flow" in props && props.flow) {
		return <FlowIconTextPresentational {...props} flow={props.flow} />;
	}

	return (
		<Suspense fallback={<Skeleton className="h-4 w-full" />}>
			<FlowIconTextFetched {...props} flowId={props.flowId} />
		</Suspense>
	);
};

type FlowIconTextFetchedProps = FlowIconTextBaseProps & {
	flowId: string;
};

const FlowIconTextFetched = ({
	flowId,
	className,
	iconSize,
	onClick,
}: FlowIconTextFetchedProps) => {
	const { data: flow } = useSuspenseQuery(buildFLowDetailsQuery(flowId));

	return (
		<FlowIconTextPresentational
			flow={flow}
			className={className}
			iconSize={iconSize}
			onClick={onClick}
		/>
	);
};

type FlowIconTextPresentationalProps = FlowIconTextBaseProps & {
	flow: Flow;
};

const FlowIconTextPresentational = ({
	flow,
	className,
	iconSize,
	onClick,
}: FlowIconTextPresentationalProps) => {
	return (
		<Link
			to="/flows/flow/$id"
			params={{ id: flow.id }}
			className={className ?? "flex items-center gap-1"}
			onClick={onClick}
		>
			<Icon
				id="Workflow"
				size={iconSize}
				className={iconSize ? undefined : "size-4"}
			/>
			{flow.name}
		</Link>
	);
};
