import { Button } from "@/components/ui/button";
import { Link } from "@tanstack/react-router";
import { PlusIcon } from "lucide-react";

export const WorkPoolsEmptyState = () => {
	return (
		<div className="flex h-[450px] flex-col items-center justify-center gap-4 rounded-lg border border-dashed">
			<div className="flex flex-col items-center gap-2 text-center">
				<h3 className="text-lg font-semibold">No work pools</h3>
				<p className="text-sm text-muted-foreground">
					Get started by creating a new work pool
				</p>
			</div>
			<Button asChild>
				<Link to="/work-pools/create">
					<PlusIcon className="mr-2 h-4 w-4" />
					Create Work Pool
				</Link>
			</Button>
		</div>
	);
};
