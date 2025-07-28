import { PollStatus } from "@/components/work-pools/poll-status";

interface PollStatusSectionProps {
	workPoolName: string;
}

export function PollStatusSection({ workPoolName }: PollStatusSectionProps) {
	return <PollStatus workPoolName={workPoolName} />;
}
