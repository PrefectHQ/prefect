import { WorkPoolIconText } from "@/components/work-pools/work-pool-icon-text";

type WorkPoolNameProps = {
	workPoolName: string;
};

export const WorkPoolName = ({ workPoolName }: WorkPoolNameProps) => {
	return <WorkPoolIconText workPoolName={workPoolName} />;
};
