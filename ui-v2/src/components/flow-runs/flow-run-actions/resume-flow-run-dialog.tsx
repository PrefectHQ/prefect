import { useQuery } from "@tanstack/react-query";
import { Suspense, useEffect } from "react";
import { toast } from "sonner";
import {
	buildGetFlowRunInputQuery,
	type FlowRun,
	useResumeFlowRun,
} from "@/api/flow-runs";
import {
	LazySchemaForm,
	type PrefectSchemaObject,
	useSchemaForm,
} from "@/components/schemas";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { LazyMarkdown } from "@/components/ui/lazy-markdown";
import { Skeleton } from "@/components/ui/skeleton";
import { StateBadge } from "@/components/ui/state-badge";

type ResumeFlowRunDialogProps = {
	flowRun: FlowRun;
	open: boolean;
	onOpenChange: (open: boolean) => void;
};

export const ResumeFlowRunDialog = ({
	flowRun,
	open,
	onOpenChange,
}: ResumeFlowRunDialogProps) => {
	// Check if this flow run requires input on resume
	const runInputKeyset = flowRun.state?.state_details?.run_input_keyset as
		| Record<string, string>
		| undefined;
	const requiresInput = runInputKeyset?.schema;

	if (requiresInput) {
		return (
			<Dialog open={open} onOpenChange={onOpenChange}>
				<DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
					<Suspense fallback={<ResumeDialogSkeleton />}>
						<ResumeDialogWithInput
							flowRun={flowRun}
							keyset={runInputKeyset}
							onOpenChange={onOpenChange}
						/>
					</Suspense>
				</DialogContent>
			</Dialog>
		);
	}

	return (
		<ResumeDialogSimple
			flowRun={flowRun}
			open={open}
			onOpenChange={onOpenChange}
		/>
	);
};

/**
 * Simple resume dialog for flows that don't require input
 */
const ResumeDialogSimple = ({
	flowRun,
	open,
	onOpenChange,
}: ResumeFlowRunDialogProps) => {
	const { resumeFlowRun, isPending } = useResumeFlowRun();

	const handleResume = () => {
		resumeFlowRun(
			{ id: flowRun.id },
			{
				onSuccess: () => {
					toast.success("Flow run resumed");
					onOpenChange(false);
				},
				onError: (error) => {
					toast.error(error.message || "Failed to resume flow run");
				},
			},
		);
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Resume Flow Run</DialogTitle>
					<DialogDescription asChild>
						<div className="space-y-4">
							<p>
								Resume the paused flow run{" "}
								<span className="font-medium">{flowRun.name}</span>?
							</p>
							<div className="flex items-center gap-2">
								<span className="text-sm text-muted-foreground">
									Current state:
								</span>
								{flowRun.state_type && flowRun.state_name && (
									<StateBadge
										type={flowRun.state_type}
										name={flowRun.state_name}
									/>
								)}
							</div>
						</div>
					</DialogDescription>
				</DialogHeader>

				<DialogFooter>
					<Button
						type="button"
						variant="outline"
						onClick={() => onOpenChange(false)}
						disabled={isPending}
					>
						Cancel
					</Button>
					<Button
						onClick={handleResume}
						disabled={isPending}
						loading={isPending}
					>
						Resume
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
};

/**
 * Resume dialog with schema-based input form
 */
type ResumeDialogWithInputProps = {
	flowRun: FlowRun;
	keyset: Record<string, string>;
	onOpenChange: (open: boolean) => void;
};

const ResumeDialogWithInput = ({
	flowRun,
	keyset,
	onOpenChange,
}: ResumeDialogWithInputProps) => {
	const { resumeFlowRun, isPending } = useResumeFlowRun();
	const { values, setValues, errors, validateForm } = useSchemaForm();

	// Fetch schema and description
	const { data: schema } = useQuery({
		...buildGetFlowRunInputQuery(flowRun.id, keyset.schema),
		select: (data) => data as PrefectSchemaObject | undefined,
	});

	const { data: description } = useQuery({
		...buildGetFlowRunInputQuery(flowRun.id, keyset.description ?? ""),
		enabled: Boolean(keyset.description),
		select: (data) => data as string | undefined,
	});

	// Reset form when dialog opens
	useEffect(() => {
		setValues({});
	}, [setValues]);

	const handleResume = async () => {
		if (!schema) return;

		try {
			// Validate the form before submitting
			await validateForm({ schema: values });

			if (errors.length > 0) {
				return;
			}

			resumeFlowRun(
				{ id: flowRun.id, runInput: values },
				{
					onSuccess: () => {
						toast.success("Flow run resumed");
						onOpenChange(false);
					},
					onError: (error) => {
						toast.error(error.message || "Failed to resume flow run");
					},
				},
			);
		} catch {
			toast.error("Failed to validate input");
		}
	};

	if (!schema) {
		return <ResumeDialogSkeleton />;
	}

	return (
		<>
			<DialogHeader>
				<DialogTitle>Resume Flow Run</DialogTitle>
				<DialogDescription asChild>
					<div className="space-y-2">
						<p>
							Provide input to resume{" "}
							<span className="font-medium">{flowRun.name}</span>
						</p>
						<div className="flex items-center gap-2">
							<span className="text-sm text-muted-foreground">
								Current state:
							</span>
							{flowRun.state_type && flowRun.state_name && (
								<StateBadge
									type={flowRun.state_type}
									name={flowRun.state_name}
								/>
							)}
						</div>
					</div>
				</DialogDescription>
			</DialogHeader>

			{description && (
				<div className="prose prose-sm dark:prose-invert max-w-none py-2 px-3 bg-muted/50 rounded-md">
					<LazyMarkdown>{description}</LazyMarkdown>
				</div>
			)}

			<div className="py-4">
				<LazySchemaForm
					schema={schema}
					values={values}
					onValuesChange={setValues}
					errors={errors}
					kinds={["json"]}
				/>
			</div>

			<DialogFooter>
				<Button
					type="button"
					variant="outline"
					onClick={() => onOpenChange(false)}
					disabled={isPending}
				>
					Cancel
				</Button>
				<Button
					onClick={() => void handleResume()}
					disabled={isPending}
					loading={isPending}
				>
					Resume
				</Button>
			</DialogFooter>
		</>
	);
};

const ResumeDialogSkeleton = () => (
	<div className="flex flex-col gap-4">
		<Skeleton className="h-6 w-48" />
		<Skeleton className="h-4 w-full" />
		<Skeleton className="h-32 w-full" />
		<div className="flex justify-end gap-2">
			<Skeleton className="h-10 w-20" />
			<Skeleton className="h-10 w-20" />
		</div>
	</div>
);
