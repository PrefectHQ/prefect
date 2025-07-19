import { useSuspenseQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { buildListWorkersQuery } from "@/api/workers";
import { SchemaForm } from "@/components/schemas/schema-form";
import type { PrefectSchemaObject } from "@/components/schemas/types/schemas";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Icon } from "@/components/ui/icons";
import { JsonInput } from "@/components/ui/json-input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface ConfigurationStepProps {
	workPoolType: string;
	value?: Record<string, unknown>;
	onChange: (value: Record<string, unknown>) => void;
}

export const ConfigurationStep = ({
	workPoolType,
	value,
	onChange,
}: ConfigurationStepProps) => {
	const { data: workersData } = useSuspenseQuery(buildListWorkersQuery());
	const [jsonError, setJsonError] = useState<string | null>(null);

	// Find the selected worker configuration
	const workerConfig = useMemo(() => {
		if (!workersData || !workPoolType) return null;

		// Search through the nested structure for the matching worker type
		// Structure is { "prefect": { "process": {...} }, "prefect-aws": { "ecs": {...} }, ... }
		for (const packageWorkers of Object.values(workersData)) {
			if (packageWorkers && typeof packageWorkers === "object") {
				for (const [, workerData] of Object.entries(packageWorkers)) {
					if (
						workerData &&
						typeof workerData === "object" &&
						"type" in workerData
					) {
						const data = workerData as {
							type?: string;
							default_base_job_configuration?: {
								variables?: unknown;
								job_configuration?: unknown;
							};
						};
						if (data.type === workPoolType) {
							return data;
						}
					}
				}
			}
		}
		return null;
	}, [workersData, workPoolType]);

	// Extract the schema from the worker configuration
	const schema = useMemo<PrefectSchemaObject | null>(() => {
		if (!workerConfig?.default_base_job_configuration?.variables) {
			return null;
		}

		// The variables property contains the JSON schema for configuration
		return workerConfig.default_base_job_configuration
			.variables as PrefectSchemaObject;
	}, [workerConfig]);

	// Use default values from the worker configuration if no value is provided
	const formValues = useMemo(() => {
		if (value) return value;
		if (!workerConfig?.default_base_job_configuration?.job_configuration)
			return {};
		return workerConfig.default_base_job_configuration
			.job_configuration as Record<string, unknown>;
	}, [value, workerConfig]);

	const baseJobTemplate = useMemo(() => {
		return {
			job_configuration: formValues,
			variables: schema,
		};
	}, [formValues, schema]);

	const hasSchemaProperties =
		schema?.properties && Object.keys(schema.properties).length > 0;

	// TODO: Fix JsonInput typing for onChange
	const handleJsonChange: React.FormEventHandler<HTMLDivElement> &
		((value: string) => void) = (value) => {
		try {
			if (typeof value !== "string") {
				return;
			}
			const parsed = JSON.parse(value) as {
				job_configuration?: Record<string, unknown>;
				variables?: unknown;
			};
			onChange(parsed as Record<string, unknown>);
			setJsonError(null);
		} catch {
			setJsonError("Invalid JSON");
		}
	};

	return (
		<div className="space-y-4">
			<p className="text-sm">
				Below you can configure defaults for deployments that use this work
				pool. Use the editor in the <strong>Advanced</strong> section to modify
				the existing configuration options, if needed.
			</p>
			<p className="text-sm">
				If you don&apos;t need to change the default configuration, click{" "}
				<strong>Create</strong> to create your work pool!
			</p>

			<div>
				<h3 className="text-lg font-medium mb-4">Base Job Template</h3>
				<Tabs defaultValue="defaults" className="w-full">
					<TabsList>
						<TabsTrigger value="defaults">Defaults</TabsTrigger>
						<TabsTrigger value="advanced">Advanced</TabsTrigger>
					</TabsList>
					<TabsContent value="defaults" className="mt-4">
						{hasSchemaProperties ? (
							<>
								<Alert className="mb-4" variant="info">
									<AlertDescription className="flex items-center gap-2">
										<Icon id="Info" className="h-4 w-4" />
										The fields below control the default values for the base job
										template. These values can be overridden by deployments.
									</AlertDescription>
								</Alert>
								<SchemaForm
									schema={schema}
									values={formValues}
									onValuesChange={(values) => {
										// Pass the complete base_job_template structure
										onChange({
											job_configuration: values,
											variables: schema,
										} as Record<string, unknown>);
									}}
									errors={[]}
									kinds={[]}
								/>
							</>
						) : (
							<Alert>
								<Icon id="Info" className="h-4 w-4" />
								<AlertDescription>
									This work pool&apos;s base job template does not have any
									customizations. To add customizations, edit the base job
									template directly with the <strong>Advanced</strong> tab.
								</AlertDescription>
							</Alert>
						)}
					</TabsContent>
					<TabsContent value="advanced" className="mt-4">
						<Alert className="mb-4">
							<Icon id="Info" className="h-4 w-4" />
							<AlertDescription>
								This is the JSON representation of the base job template. A work
								pool&apos;s job template controls infrastructure configuration
								for all flow runs in the work pool, and specifies the
								configuration that can be overridden by deployments.
								<br />
								<br />
								For more information on the structure of a work pool&apos;s base
								job template, check out{" "}
								<a
									href="https://docs.prefect.io/latest/concepts/work-pools/"
									target="_blank"
									rel="noopener noreferrer"
									className="text-blue-600 hover:underline"
								>
									the docs
								</a>
								.
							</AlertDescription>
						</Alert>
						<div className="space-y-2">
							<Label htmlFor="json-editor">
								{jsonError && (
									<span className="text-sm text-destructive ml-2">
										{jsonError}
									</span>
								)}
							</Label>
							<JsonInput
								id="json-editor"
								value={JSON.stringify(baseJobTemplate, null, 2)}
								onChange={handleJsonChange}
								className="min-h-[400px]"
							/>
						</div>
					</TabsContent>
				</Tabs>
			</div>
		</div>
	);
};
