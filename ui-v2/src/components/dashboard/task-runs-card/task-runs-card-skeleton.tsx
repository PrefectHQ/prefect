import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function TaskRunsCardSkeleton() {
	return (
		<Card>
			<CardHeader className="flex flex-row items-center justify-between">
				<Skeleton className="h-6 w-24" />
			</CardHeader>
			<CardContent>
				<div className="space-y-4">
					<div className="grid gap-1">
						<Skeleton className="h-5 w-20" />
						<Skeleton className="h-4 w-32" />
						<Skeleton className="h-4 w-28" />
					</div>
					<Skeleton className="h-16 w-full" />
				</div>
			</CardContent>
		</Card>
	);
}
