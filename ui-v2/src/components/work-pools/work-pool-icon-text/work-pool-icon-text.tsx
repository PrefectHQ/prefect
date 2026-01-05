import { Link } from "@tanstack/react-router";
import { Icon } from "@/components/ui/icons";

type WorkPoolIconTextProps = {
	workPoolName: string;
};

export const WorkPoolIconText = ({ workPoolName }: WorkPoolIconTextProps) => {
	return (
		<Link
			to="/work-pools/work-pool/$workPoolName"
			params={{ workPoolName }}
			className="flex items-center gap-1"
		>
			<Icon id="Cpu" className="size-4" />
			{workPoolName}
		</Link>
	);
};
