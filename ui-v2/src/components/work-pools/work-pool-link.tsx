import { Link } from "@tanstack/react-router";
import { Icon } from "@/components/ui/icons";

type WorkPoolLinkProps = {
	workPoolName: string;
};

export const WorkPoolLink = ({ workPoolName }: WorkPoolLinkProps) => {
	return (
		<div className="flex items-center gap-1 text-xs">
			Work Pool
			<Link
				to="/work-pools/work-pool/$workPoolName"
				params={{ workPoolName }}
				className="flex items-center gap-1"
			>
				<Icon id="Cpu" className="size-4" />
				{workPoolName}
			</Link>
		</div>
	);
};
