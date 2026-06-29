import { ExternalLink } from "lucide-react";
import { CodeBanner } from "@/components/code-banner";
import {
	EmptyState,
	EmptyStateActions,
	EmptyStateDescription,
	EmptyStateIcon,
	EmptyStateTitle,
} from "@/components/ui/empty-state";
import { cn } from "@/utils";
import {
	categorizeWorkPoolType,
	getWorkPoolSetupInstructions,
} from "../../work-pool-setup-instructions";

export type WorkersTableEmptyStateProps = {
	hasSearchQuery: boolean;
	workPoolName: string;
	workPoolType: string;
	className?: string;
};

export const WorkersTableEmptyState = ({
	hasSearchQuery,
	workPoolName,
	workPoolType,
	className,
}: WorkersTableEmptyStateProps) => {
	if (hasSearchQuery) {
		return (
			<EmptyState>
				<EmptyStateIcon id="Search" />
				<EmptyStateTitle>No workers found</EmptyStateTitle>
				<EmptyStateDescription>
					No workers match your search criteria.
				</EmptyStateDescription>
			</EmptyState>
		);
	}

	const category = categorizeWorkPoolType(workPoolType);
	const instructions = getWorkPoolSetupInstructions(workPoolName, workPoolType);

	if (category === "managed") {
		return (
			<EmptyState>
				<EmptyStateIcon id="Bot" />
				<EmptyStateTitle>No workers needed</EmptyStateTitle>
				<EmptyStateDescription>
					Prefect manages the infrastructure for this work pool. No workers are
					required.
				</EmptyStateDescription>
			</EmptyState>
		);
	}

	if (category === "push") {
		return (
			<EmptyState>
				<EmptyStateIcon id="Bot" />
				<EmptyStateTitle>No workers needed</EmptyStateTitle>
				<EmptyStateDescription>
					This is a push work pool — runs are submitted directly to your cloud
					infrastructure. No workers are required.
				</EmptyStateDescription>
				<EmptyStateActions>
					<a
						href={instructions.docsUrl}
						target="_blank"
						rel="noreferrer"
						className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
					>
						View setup docs <ExternalLink className="size-3" />
					</a>
				</EmptyStateActions>
			</EmptyState>
		);
	}

	return (
		<div className={cn("space-y-4", className)}>
			<EmptyState>
				<EmptyStateIcon id="Bot" />
				<EmptyStateTitle>No workers running</EmptyStateTitle>
				<EmptyStateDescription>
					No workers are currently running for the &ldquo;{workPoolName}&rdquo;
					work pool.
				</EmptyStateDescription>
				{instructions.command && (
					<EmptyStateActions>
						<CodeBanner
							command={instructions.command}
							title={instructions.title}
							subtitle={instructions.description}
						/>
					</EmptyStateActions>
				)}
			</EmptyState>
		</div>
	);
};
