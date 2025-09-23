import { Plus, Search } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils";
import { WorkPoolQueueCreateDialog } from "../../work-pool-queue-create-dialog";

type WorkPoolQueuesTableToolbarProps = {
	searchQuery: string;
	onSearchChange: (query: string) => void;
	resultsCount: number;
	totalCount: number;
	workPoolName: string;
	className?: string;
};

export const WorkPoolQueuesTableToolbar = ({
	searchQuery,
	onSearchChange,
	resultsCount,
	totalCount,
	workPoolName,
	className,
}: WorkPoolQueuesTableToolbarProps) => {
	const [showCreateDialog, setShowCreateDialog] = useState(false);
	const showClearFilters = searchQuery.length > 0;

	return (
		<div className={cn("space-y-4", className)}>
			{/* Main toolbar */}
			<div className="flex items-center justify-between">
				<div className="flex items-center space-x-2">
					<div className="text-sm text-muted-foreground">
						{searchQuery
							? `${resultsCount} of ${totalCount} Work Queue${totalCount !== 1 ? "s" : ""}`
							: `${totalCount} Work Queue${totalCount !== 1 ? "s" : ""}`}
					</div>
					<Button
						variant="ghost"
						size="sm"
						onClick={() => setShowCreateDialog(true)}
					>
						<Plus className="h-4 w-4" />
					</Button>
				</div>

				<div className="flex items-center space-x-2">
					{showClearFilters && (
						<Button
							variant="ghost"
							size="sm"
							onClick={() => onSearchChange("")}
						>
							Clear filters
						</Button>
					)}
					<div className="relative">
						<Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
						<Input
							placeholder="Search"
							value={searchQuery}
							onChange={(e) => onSearchChange(e.target.value)}
							className="pl-8 w-64"
						/>
					</div>
				</div>
			</div>

			<WorkPoolQueueCreateDialog
				workPoolName={workPoolName}
				open={showCreateDialog}
				onOpenChange={setShowCreateDialog}
				onSubmit={() => setShowCreateDialog(false)}
			/>
		</div>
	);
};
