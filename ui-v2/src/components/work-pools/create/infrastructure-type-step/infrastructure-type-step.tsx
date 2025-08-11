import { useSuspenseQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useFormContext } from "react-hook-form";
import { buildListWorkPoolTypesQuery } from "@/api/collections/collections";
import { Badge } from "@/components/ui/badge";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { LogoImage } from "@/components/ui/logo-image";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { titleCase } from "@/utils";

type WorkPoolTypeSelectOption = {
	label: string;
	value: string;
	logoUrl: string;
	description: string;
	documentationUrl?: string;
	isBeta: boolean;
};

export function InfrastructureTypeStep() {
	const form = useFormContext();
	const { data: workersResponse = {} } = useSuspenseQuery(
		buildListWorkPoolTypesQuery(),
	);

	const options = useMemo<WorkPoolTypeSelectOption[]>(() => {
		const options: WorkPoolTypeSelectOption[] = [];

		// Transform the workers response to options array
		Object.values(workersResponse).forEach((collection) => {
			if (collection && typeof collection === "object") {
				Object.values(collection).forEach((worker) => {
					if (worker && typeof worker === "object" && "type" in worker) {
						const {
							type,
							display_name: displayName,
							description,
							logo_url: logoUrl,
							documentation_url: documentationUrl,
							is_beta: isBeta,
						} = worker as {
							type?: string;
							display_name?: string;
							description?: string;
							logo_url?: string;
							documentation_url?: string;
							is_beta?: boolean;
						};

						if (type && logoUrl && description) {
							options.push({
								label: displayName || titleCase(type),
								value: type,
								logoUrl,
								description,
								documentationUrl,
								isBeta: isBeta || false,
							});
						}
					}
				});
			}
		});

		// Sort options: non-beta first, then alphabetically by label
		return options.sort((firstOption, secondOption) => {
			if (firstOption.isBeta && !secondOption.isBeta) {
				return 1;
			}
			if (!firstOption.isBeta && secondOption.isBeta) {
				return -1;
			}
			return firstOption.label.localeCompare(secondOption.label);
		});
	}, [workersResponse]);

	return (
		<FormField
			control={form.control}
			name="type"
			render={({ field, fieldState }) => (
				<FormItem>
					<FormLabel className="text-base font-medium">
						Select the infrastructure you want to use to execute your flow runs
					</FormLabel>
					<FormControl>
						<RadioGroup
							value={field.value as string}
							onValueChange={(value: string) => field.onChange(value)}
							className="space-y-3"
						>
							{options.map(({ label, value, logoUrl, description, isBeta }) => (
								<div
									key={value}
									className="flex items-center space-x-3 p-4 rounded-lg border hover:bg-accent/50"
								>
									<RadioGroupItem value={value} id={value} />
									<label htmlFor={value} className="flex-1 cursor-pointer">
										<div className="flex items-center gap-4">
											<LogoImage url={logoUrl} alt={label} size="md" />
											<div className="flex flex-col gap-2 flex-1">
												<p className="text-base font-medium flex items-center">
													{label}
													{isBeta && (
														<Badge variant="secondary" className="ml-2 text-xs">
															Beta
														</Badge>
													)}
												</p>
												<p className="text-sm text-muted-foreground">
													{description}
												</p>
											</div>
										</div>
									</label>
								</div>
							))}
						</RadioGroup>
					</FormControl>
					{fieldState.error && (
						<FormMessage>{fieldState.error.message}</FormMessage>
					)}
				</FormItem>
			)}
		/>
	);
}
