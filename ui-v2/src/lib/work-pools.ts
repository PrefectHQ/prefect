export type WorkPoolStatus = "ready" | "paused" | "not_ready";

export interface WorkPoolStatusInfo {
	status: WorkPoolStatus;
	label: string;
	description: string;
	variant: "default" | "secondary" | "destructive" | "outline";
}

export const getWorkPoolStatusInfo = (
	status: WorkPoolStatus,
): WorkPoolStatusInfo => {
	const statusMap: Record<WorkPoolStatus, WorkPoolStatusInfo> = {
		ready: {
			status: "ready",
			label: "Ready",
			description: "Work pool is ready and accepting work",
			variant: "default",
		},
		paused: {
			status: "paused",
			label: "Paused",
			description: "Work pool is paused",
			variant: "secondary",
		},
		not_ready: {
			status: "not_ready",
			label: "Not Ready",
			description: "Work pool is not ready",
			variant: "destructive",
		},
	};

	return statusMap[status];
};

export const isWorkPoolReady = (status: WorkPoolStatus): boolean => {
	return status === "ready";
};
