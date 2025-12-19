import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { useUpdateWorkPool, type WorkPool } from "@/api/work-pools";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { BaseJobTemplateFormSection } from "../create/infrastructure-configuration-step/base-job-template-form-section";
import {
	type WorkerBaseJobTemplate,
	type WorkPoolEditFormValues,
	workPoolEditSchema,
} from "./schema";

type WorkPoolEditFormProps = {
	workPool: WorkPool;
};

export const WorkPoolEditForm = ({ workPool }: WorkPoolEditFormProps) => {
	const router = useRouter();
	const { updateWorkPool, isPending } = useUpdateWorkPool();

	const form = useForm<WorkPoolEditFormValues>({
		resolver: zodResolver(workPoolEditSchema),
		defaultValues: {
			description: workPool.description ?? "",
			concurrencyLimit: workPool.concurrency_limit ?? null,
			baseJobTemplate: workPool.base_job_template as Record<string, unknown>,
		},
	});

	const baseJobTemplate = form.watch("baseJobTemplate") as
		| WorkerBaseJobTemplate
		| undefined;
	const showBaseJobTemplateSection = workPool.type !== "prefect-agent";

	const handleCancel = () => {
		router.history.back();
	};

	const handleSubmit = (data: WorkPoolEditFormValues) => {
		updateWorkPool(
			{
				name: workPool.name,
				workPool: {
					description: data.description || null,
					concurrency_limit: data.concurrencyLimit,
					base_job_template: data.baseJobTemplate,
				},
			},
			{
				onSuccess: () => {
					toast.success("Work pool updated");
					void router.navigate({
						to: "/work-pools/work-pool/$workPoolName",
						params: { workPoolName: workPool.name },
					});
				},
				onError: (error) => {
					toast.error(
						`Failed to update work pool: ${error instanceof Error ? error.message : "Unknown error"}`,
					);
				},
			},
		);
	};

	return (
		<Form {...form}>
			<form
				onSubmit={(e) => void form.handleSubmit(handleSubmit)(e)}
				className="space-y-6"
			>
				<Card>
					<CardContent className="pt-6 space-y-6">
						<div className="space-y-2">
							<Label htmlFor="work-pool-name">Name</Label>
							<Input id="work-pool-name" value={workPool.name} disabled />
						</div>

						<FormField
							control={form.control}
							name="description"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Description (Optional)</FormLabel>
									<FormControl>
										<Textarea
											{...field}
											value={field.value ?? ""}
											rows={7}
											placeholder="Enter a description for your work pool"
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="concurrencyLimit"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Flow Run Concurrency (Optional)</FormLabel>
									<FormControl>
										<Input
											{...field}
											type="number"
											min={0}
											placeholder="Unlimited"
											value={field.value ?? ""}
											onChange={(e) => {
												const value = e.target.value;
												field.onChange(value === "" ? null : Number(value));
											}}
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						<div className="space-y-2">
							<Label htmlFor="work-pool-type">Type</Label>
							<Input id="work-pool-type" value={workPool.type} disabled />
						</div>
					</CardContent>
				</Card>

				{showBaseJobTemplateSection && (
					<BaseJobTemplateFormSection
						baseJobTemplate={baseJobTemplate}
						onBaseJobTemplateChange={(value) => {
							form.setValue("baseJobTemplate", value);
						}}
					/>
				)}

				<div className="flex justify-end gap-2">
					<Button
						type="button"
						variant="outline"
						onClick={handleCancel}
						disabled={isPending}
					>
						Cancel
					</Button>
					<Button type="submit" disabled={isPending}>
						{isPending ? "Saving..." : "Save"}
					</Button>
				</div>
			</form>
		</Form>
	);
};
