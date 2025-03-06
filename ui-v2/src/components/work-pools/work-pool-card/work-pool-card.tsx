import { WorkPool } from "@/api/work-pools";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { WorkPoolName } from "./components/work-pool-name";
import { WorkPoolTypeBadge } from "./components/work-pool-type-badge";
type WorkPoolCardProps = {
	workPool: WorkPool;
};

export const WorkPoolCard = ({ workPool }: WorkPoolCardProps) => {
	return (
		<Card className="gap-2">
			<CardHeader>
				<CardTitle className="flex items-center gap-2">
					<WorkPoolName workPoolName={workPool.name} />
					{workPool.status && <StatusBadge status={workPool.status} />}
				</CardTitle>
			</CardHeader>
			<CardContent className="flex flex-col gap-1">
				<div className="flex items-center gap-1">
					<WorkPoolTypeBadge type={workPool.type} />
				</div>
				<div className="text-sm">
					Concurrency:{" "}
					{workPool.concurrency_limit
						? workPool.concurrency_limit
						: "Unlimited"}
				</div>
			</CardContent>
		</Card>
	);
};
