import { buildFLowDetailsQuery } from "@/api/flows";
import { Icon } from "@/components/ui/icons";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

type DeploymentFlowLinkProps = {
	flowId: string;
};

export const DeploymentFlowLink = ({ flowId }: DeploymentFlowLinkProps) => {
	const { data } = useQuery(buildFLowDetailsQuery(flowId));

	return (
		<div className="flex items-center gap-1 text-sm">
			Flow
			<Link
				to="/flows/flow/$id"
				params={{ id: flowId }}
				className="flex items-center gap-1"
			>
				<Icon id="Workflow" className="h-4 w-4" />
				{data?.name}
			</Link>
		</div>
	);
};
