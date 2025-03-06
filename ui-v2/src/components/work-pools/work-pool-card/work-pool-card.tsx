import { WorkPool } from "@/api/work-pools";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { WorkPoolName } from "./components/work-pool-name";
import { WorkPoolTypeBadge } from "./components/work-pool-type-badge";
type WorkPoolCardProps = {
	workPool: WorkPool;
};

export const WorkPoolCard = ({ workPool }: WorkPoolCardProps) => {
	return (
		<Card>
			<CardHeader>
				<CardTitle>
					<WorkPoolName workPoolName={workPool.name} />
				</CardTitle>
			</CardHeader>
			<CardContent>
				<WorkPoolTypeBadge type={workPool.type} />
				<Badge>{workPool.status}</Badge>
				<Badge>{workPool.concurrency_limit}</Badge>
			</CardContent>
		</Card>
	);
};
