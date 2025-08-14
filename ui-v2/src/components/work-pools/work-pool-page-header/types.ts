import type { WorkPool } from "@/api/work-pools";

export interface PageHeadingWorkPoolProps {
	workPool: WorkPool;
	onUpdate?: () => void;
	className?: string;
}
