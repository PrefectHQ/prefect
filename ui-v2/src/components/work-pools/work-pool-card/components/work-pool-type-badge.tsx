import type { WorkPool } from "@/api/work-pools";
import { Badge } from "@/components/ui/badge";
import { Icon, type IconId } from "@/components/ui/icons";

type WorkPoolTypeBadgeProps = {
	type: WorkPool["type"];
};

const WORK_POOL_TYPE_LABELS: Record<WorkPool["type"], string> = {
	process: "Process",
	ecs: "ECS",
	"azure-container-instance": "Azure Container Instance",
	docker: "Docker",
	"cloud-run": "Cloud Run",
	"cloud-run-v2": "Cloud Run v2",
	"vertex-ai": "Vertex AI",
	kubernetes: "Kubernetes",
} as const;

const WORK_POOL_TYPE_ICONS: Record<WorkPool["type"], IconId> = {
	process: "Cpu",
	ecs: "Cpu",
	"azure-container-instance": "Cpu",
	docker: "Cpu",
	"cloud-run": "Cpu",
	"cloud-run-v2": "Cpu",
	"vertex-ai": "Cpu",
	kubernetes: "Cpu",
} as const;

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
