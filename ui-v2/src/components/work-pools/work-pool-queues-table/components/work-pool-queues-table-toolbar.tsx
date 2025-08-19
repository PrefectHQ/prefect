import { Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type WorkPoolQueuesTableToolbarProps = {
	searchQuery: string;
	onSearchChange: (query: string) => void;
	resultsCount: number;
	totalCount: number;
	workPoolName: string;
	className?: string;
}

export const WorkPoolQueuesTableToolbar = ({
	searchQuery,
	onSearchChange,
	resultsCount,
	totalCount,
	workPoolName,
	className,
}: WorkPoolQueuesTableToolbarProps) => {
	const showClearFilters = searchQuery.length > 0;

	return (
		<div className={cn("flex items-center justify-between", className)}>
			<div className="flex items-center space-x-2">
				<div className="relative">
					<Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
					<Input
						placeholder="Search queues..."
						value={searchQuery}
						onChange={(e) => onSearchChange(e.target.value)}
						className="pl-8 w-64"
					/>
				</div>
				{showClearFilters && (
					<Button variant="ghost" size="sm" onClick={() => onSearchChange("")}>
						Clear filters
					</Button>
				)}
			</div>

			<div className="flex items-center space-x-4">
				<div className="text-sm text-muted-foreground">
					{searchQuery
						? `${resultsCount} of ${totalCount} queues`
						: `${totalCount} queues`}
				</div>
				<Button
					onClick={() => {
						// TODO: Navigate to create queue page when route exists
						console.log("Create queue for pool:", workPoolName);
					}}
					size="sm"
				>
					<Plus className="h-4 w-4 mr-2" />
					Create Queue
				</Button>
			</div>
		</div>
	);
};
