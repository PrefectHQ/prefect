import { WorkPool } from "@/api/work-pools";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icons";
import { WORK_POOL_TYPE_ICONS, WORK_POOL_TYPE_LABELS } from "../../constants";

type WorkPoolTypeBadgeProps = {
	type: WorkPool["type"];
};

const getWorkPoolTypeLabel = (type: WorkPool["type"]) => {
	return WORK_POOL_TYPE_LABELS[type] ?? type;
};

const getWorkPoolTypeIcon = (type: WorkPool["type"]) => {
	return WORK_POOL_TYPE_ICONS[type] ?? "Cpu";
};

export const WorkPoolTypeBadge = ({ type }: WorkPoolTypeBadgeProps) => {
	return (
		<Badge>
			<Icon id={getWorkPoolTypeIcon(type)} />
			{getWorkPoolTypeLabel(type)}
		</Badge>
	);
};
