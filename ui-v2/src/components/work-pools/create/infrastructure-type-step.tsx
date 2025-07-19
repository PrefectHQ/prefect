import { useSuspenseQuery } from "@tanstack/react-query";
import { buildListWorkersQuery } from "@/api/workers";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { WorkerCollectionItem } from "./types";

interface InfrastructureTypeStepProps {
	value?: string;
	onChange: (value: string) => void;
}

export const InfrastructureTypeStep = ({
	value,
	onChange,
}: InfrastructureTypeStepProps) => {
	const { data: workersData } = useSuspenseQuery(buildListWorkersQuery());

	// Transform the nested API response into a flat array of workers
	const workers: WorkerCollectionItem[] = [];

	if (workersData && typeof workersData === "object") {
		// The structure is { "prefect": { "process": {...} }, "prefect-aws": { "ecs": {...} }, ... }
		Object.entries(workersData).forEach(([, packageWorkers]) => {
			if (packageWorkers && typeof packageWorkers === "object") {
				Object.entries(packageWorkers).forEach(
					([workerType, workerData]: [string, unknown]) => {
						if (
							workerData &&
							typeof workerData === "object" &&
							"type" in workerData
						) {
							const data = workerData as {
								type?: string;
								display_name?: string;
								description?: string;
								documentation_url?: string;
								logo_url?: string;
								is_beta?: boolean;
								default_base_job_configuration?: {
									job_configuration?: unknown;
								};
							};
							workers.push({
								type: data.type || workerType,
								displayName: data.display_name,
								description: data.description,
								documentationUrl: data.documentation_url,
								logoUrl: data.logo_url,
								isBeta: data.is_beta,
								defaultBaseJobConfiguration: data.default_base_job_configuration
									?.job_configuration as Record<string, unknown> | undefined,
							});
						}
					},
				);
			}
		});
	}

	// Sort workers: non-beta first, then alphabetically by display name
	const sortedWorkers = workers.sort((a, b) => {
		if (a.isBeta && !b.isBeta) return 1;
		if (!a.isBeta && b.isBeta) return -1;
		return (a.displayName || a.type).localeCompare(b.displayName || b.type);
	});

	return (
		<div className="space-y-4">
			<div>
				<h3 className="text-lg font-medium">Select Infrastructure Type</h3>
				<p className="text-sm text-muted-foreground mt-1">
					Choose the infrastructure you want to use to execute your flow runs
				</p>
			</div>

			<div className="space-y-3">
				{sortedWorkers.map((worker) => (
					<Card
						key={worker.type}
						className={cn(
							"cursor-pointer transition-colors px-6",
							value === worker.type
								? "border-primary"
								: "hover:border-primary/50",
						)}
						onClick={() => onChange(worker.type)}
					>
						<div className="flex items-center gap-4">
							<input
								type="radio"
								name="infrastructure-type"
								value={worker.type}
								checked={value === worker.type}
								className="flex-shrink-0"
								id={worker.type}
							/>
							{worker.logoUrl && (
								<img
									src={worker.logoUrl}
									alt={`${worker.displayName || worker.type} logo`}
									className="w-8 h-8 object-contain flex-shrink-0"
								/>
							)}
							<Label htmlFor={worker.type} className="flex-1 cursor-pointer">
								<div className="space-y-1">
									<div className="flex items-center gap-2">
										<span className="font-medium text-base">
											{worker.displayName || worker.type}
										</span>
										{worker.isBeta && (
											<Badge variant="secondary" className="text-xs">
												Beta
											</Badge>
										)}
									</div>
									{worker.description && (
										<p className="text-sm text-muted-foreground">
											{worker.description}
										</p>
									)}
								</div>
							</Label>
						</div>
					</Card>
				))}
			</div>
		</div>
	);
};
