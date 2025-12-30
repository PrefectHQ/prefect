import { WorkQueueIconText } from "./work-queue-icon-text";

type WorkQueueLinkProps = {
	workPoolName: string;
	workQueueName: string;
	className?: string;
	iconSize?: number;
};

export const WorkQueueLink = (props: WorkQueueLinkProps) => (
	<WorkQueueIconText {...props} showLabel showStatus />
);
