import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function FlowRunsCardSkeleton() {
	return (
		<Card>
			<CardHeader className="flex flex-row items-center justify-between">
				<Skeleton className="h-6 w-24" />
				<Skeleton className="h-4 w-16" />
			</CardHeader>
			<CardContent className="space-y-2">
				<Skeleton className="h-24 w-full" />
				<div className="flex justify-between w-full gap-2">
					{[1, 2, 3, 4, 5].map((i) => (
						<Skeleton key={i} className="h-10 flex-1" />
					))}
				</div>
				<Skeleton className="h-32 w-full" />
			</CardContent>
		</Card>
	);
}
