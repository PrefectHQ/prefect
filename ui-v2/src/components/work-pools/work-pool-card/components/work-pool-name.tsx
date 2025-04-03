import { Link } from "@tanstack/react-router";

type WorkPoolNameProps = {
	workPoolName: string;
};

export const WorkPoolName = ({ workPoolName }: WorkPoolNameProps) => {
	return (
		<Link
			to="/work-pools/work-pool/$workPoolName"
			params={{ workPoolName }}
			className="flex items-center gap-1"
		>
			{workPoolName}
		</Link>
	);
};
