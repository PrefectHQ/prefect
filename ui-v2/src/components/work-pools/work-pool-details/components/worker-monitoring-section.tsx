import { WorkerMonitoring } from "@/components/work-pools/worker-monitoring";

interface WorkerMonitoringSectionProps {
	workPoolName: string;
}

export function WorkerMonitoringSection({
	workPoolName,
}: WorkerMonitoringSectionProps) {
	return <WorkerMonitoring workPoolName={workPoolName} />;
}
