import { WorkPool } from "@/api/work-pools";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { WorkPoolName } from "./components/work-pool-name";

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
		</Card>
	);
};
