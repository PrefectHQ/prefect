import type { WorkPool } from "@/api/work-pools";

export interface WorkPoolDetailsProps {
	workPool: WorkPool;
	alternate?: boolean;
	className?: string;
}

export interface WorkPoolJobTemplate {
	job_configuration?: Record<string, unknown>;
	variables?: Record<string, VariableSchema>;
}

export interface VariableSchema {
	type?: string;
	default?: unknown;
	description?: string;
	title?: string;
}
