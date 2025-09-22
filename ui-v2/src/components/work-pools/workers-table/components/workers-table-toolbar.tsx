import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils";

export type WorkersTableToolbarProps = {
	searchQuery: string;
	onSearchChange: (query: string) => void;
	resultsCount: number;
	totalCount: number;
	className?: string;
};

export const WorkersTableToolbar = ({
	searchQuery,
	onSearchChange,
	resultsCount,
	totalCount,
	className,
}: WorkersTableToolbarProps) => {
	const showClearFilters = searchQuery.length > 0;

	return (
		<div className={cn("flex items-center justify-between", className)}>
			<div className="text-sm text-muted-foreground">
				{searchQuery
					? `${resultsCount} of ${totalCount} workers`
					: `${totalCount} workers`}
			</div>
			<div className="flex items-center space-x-2">
				{showClearFilters && (
					<Button variant="ghost" size="sm" onClick={() => onSearchChange("")}>
						Clear filters
					</Button>
				)}
				<Input
					placeholder="Search workers..."
					value={searchQuery}
					onChange={(e) => onSearchChange(e.target.value)}
					className="w-64"
				/>
			</div>
		</div>
	);
};
