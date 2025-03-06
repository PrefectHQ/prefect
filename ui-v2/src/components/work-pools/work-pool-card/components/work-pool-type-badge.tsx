import { WorkPool } from "@/api/work-pools";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icons";
import { WORK_POOL_TYPE_ICONS, WORK_POOL_TYPE_LABELS } from "../../constants";

type WorkPoolTypeBadgeProps = {
	type: WorkPool["type"];
};

export const WorkPoolTypeBadge = ({ type }: WorkPoolTypeBadgeProps) => {
	console.log(type);
	return (
		<Badge>
			<Icon id={WORK_POOL_TYPE_ICONS[type]} />
			{WORK_POOL_TYPE_LABELS[type]}
		</Badge>
	);
};
