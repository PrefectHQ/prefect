import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function WorkPoolsCardSkeleton() {
	return (
		<Card>
			<CardHeader>
				<Skeleton className="h-6 w-32 mb-4" />
			</CardHeader>
			<CardContent>
				<div className="flex flex-col gap-4">
					{/* Render 2 skeleton work pool cards */}
					{[1, 2].map((i) => (
						<div
							key={i}
							className="rounded-xl border border-border p-3 space-y-3"
						>
							<div className="flex items-center gap-2">
								<Skeleton className="h-5 w-32" />
								<Skeleton className="h-5 w-5 rounded-full" />
							</div>
							<div className="grid grid-cols-4 gap-2">
								{[1, 2, 3, 4].map((j) => (
									<div key={j} className="flex flex-col items-center space-y-1">
										<Skeleton className="h-3 w-16" />
										<Skeleton className="h-4 w-12" />
									</div>
								))}
							</div>
						</div>
					))}
				</div>
			</CardContent>
		</Card>
	);
}
