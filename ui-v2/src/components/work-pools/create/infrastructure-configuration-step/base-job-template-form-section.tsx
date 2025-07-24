import { useCallback, useMemo, useState } from "react";
import { useSchemaFormErrors } from "@/components/schemas/hooks/useSchemaFormErrors";
import { useSchemaFormValues } from "@/components/schemas/hooks/useSchemaValues";
import { SchemaForm } from "@/components/schemas/schema-form";
import type { PrefectSchemaObject } from "@/components/schemas/types/schemas";
import type { SchemaFormValues } from "@/components/schemas/types/values";
import { Card, CardContent, CardDescription } from "@/components/ui/card";
import { JsonInput, type JsonInputOnChange } from "@/components/ui/json-input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Typography } from "@/components/ui/typography";
import type { WorkerBaseJobTemplate } from "./schema";

type BaseJobTemplateFormSectionProps = {
	baseJobTemplate?: WorkerBaseJobTemplate;
	onBaseJobTemplateChange: (value: WorkerBaseJobTemplate) => void;
};

export function BaseJobTemplateFormSection({
	baseJobTemplate,
	onBaseJobTemplateChange,
}: BaseJobTemplateFormSectionProps) {
	const [jsonValue, setJsonValue] = useState(() =>
		JSON.stringify(baseJobTemplate || {}, null, 2),
	);
	const [jsonError, setJsonError] = useState<string | null>(null);

	const variablesSchema = useMemo<PrefectSchemaObject | undefined>(() => {
		return baseJobTemplate?.variables as PrefectSchemaObject;
	}, [baseJobTemplate?.variables]);

	const hasSchemaProperties = useMemo(() => {
		return (
			variablesSchema?.properties &&
			Object.keys(variablesSchema.properties).length > 0
		);
	}, [variablesSchema?.properties]);

	// Get default values from schema properties
	const defaultValues = useMemo<SchemaFormValues>(() => {
		if (!variablesSchema?.properties) return {};

		const defaults: SchemaFormValues = {};
		Object.entries(variablesSchema.properties).forEach(([key, property]) => {
			if (property && typeof property === "object" && "default" in property) {
				defaults[key] = property.default;
			}
		});
		return defaults;
	}, [variablesSchema?.properties]);

	const [schemaValues, setSchemaValues] = useSchemaFormValues(defaultValues);
	const [schemaErrors] = useSchemaFormErrors([]);

	const handleSchemaValuesChange = useCallback(
		(values: SchemaFormValues) => {
			setSchemaValues(values);

			if (!variablesSchema?.properties) return;

			// Update the base job template with new default values
			const newTemplate: WorkerBaseJobTemplate = {
				...baseJobTemplate,
				variables: {
					...variablesSchema,
					properties: Object.fromEntries(
						Object.entries(variablesSchema.properties).map(
							([key, property]) => [
								key,
								{
									...property,
									default: values[key],
								},
							],
						),
					),
				},
			};

			onBaseJobTemplateChange(newTemplate);
			setJsonValue(JSON.stringify(newTemplate, null, 2));
		},
		[
			baseJobTemplate,
			variablesSchema,
			onBaseJobTemplateChange,
			setSchemaValues,
		],
	);

	const handleJsonChange = useCallback(
		(value: string) => {
			setJsonValue(value);
			setJsonError(null);

			try {
				const parsed = JSON.parse(value) as WorkerBaseJobTemplate;
				onBaseJobTemplateChange(parsed);
			} catch (error) {
				setJsonError(error instanceof Error ? error.message : "Invalid JSON");
			}
		},
		[onBaseJobTemplateChange],
	);

	return (
		<div className="space-y-4">
			<Typography variant="h3">Base Job Template</Typography>

			<Tabs defaultValue="defaults" className="w-full">
				<TabsList>
					<TabsTrigger value="defaults">Defaults</TabsTrigger>
					<TabsTrigger value="advanced">Advanced</TabsTrigger>
				</TabsList>

				<TabsContent value="defaults" className="space-y-4">
					{hasSchemaProperties ? (
						<>
							<Card>
								<CardContent>
									<CardDescription>
										The fields below control the default values for the base job
										template. These values can be overridden by deployments.
									</CardDescription>
								</CardContent>
							</Card>

							{variablesSchema && (
								<SchemaForm
									schema={variablesSchema}
									kinds={["json"]}
									values={schemaValues}
									onValuesChange={handleSchemaValuesChange}
									errors={schemaErrors}
								/>
							)}
						</>
					) : (
						<Card>
							<CardContent>
								<CardDescription>
									This work pool&apos;s base job template does not have any
									customizations. To add customizations, edit the base job
									template directly with the <strong>Advanced</strong> tab.
								</CardDescription>
							</CardContent>
						</Card>
					)}
				</TabsContent>

				<TabsContent value="advanced" className="space-y-4">
					<Card>
						<CardContent>
							<CardDescription>
								This is the JSON representation of the base job template. A work
								pool&apos;s job template controls infrastructure configuration
								for all flow runs in the work pool, and specifies the
								configuration that can be overridden by deployments.
								<br />
								<br />
								For more information on the structure of a work pool&apos;s base
								job template, check out the docs.
							</CardDescription>
						</CardContent>
					</Card>

					<div className="space-y-2">
						<Label>Base Job Template JSON</Label>
						<JsonInput
							value={jsonValue}
							onChange={handleJsonChange as JsonInputOnChange}
							className={jsonError ? "border-destructive" : ""}
						/>
						{jsonError && (
							<p className="text-sm text-destructive">{jsonError}</p>
						)}
					</div>
				</TabsContent>
			</Tabs>
		</div>
	);
}
