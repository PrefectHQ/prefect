import { WorkPool } from "@/api/work-pools";
import { IconId } from "../ui/icons";

export const WORK_POOL_TYPE_LABELS: Record<WorkPool["type"], string> = {
	process: "Process",
	ecs: "ECS",
	"azure-container-instance": "Azure Container Instance",
	docker: "Docker",
	"cloud-run": "Cloud Run",
	"cloud-run-v2": "Cloud Run v2",
	"google-vertex-ai": "Vertex AI",
	kubernetes: "Kubernetes",
} as const;

export const WORK_POOL_TYPE_ICONS: Record<WorkPool["type"], IconId> = {
	process: "Cpu",
	ecs: "Cpu",
	"azure-container-instance": "Cpu",
	docker: "Cpu",
	"cloud-run": "Cpu",
	"cloud-run-v2": "Cpu",
	"google-vertex-ai": "Cpu",
	kubernetes: "Cpu",
} as const;
