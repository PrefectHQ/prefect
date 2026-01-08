import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useFormContext } from "react-hook-form";
import { useValidateTemplate } from "@/api/automations";
import {
	type BlockDocument,
	buildListFilterBlockDocumentsQuery,
} from "@/api/block-documents";
import { buildListFilterBlockTypesQuery } from "@/api/block-types";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import {
	Combobox,
	ComboboxCommandEmtpy,
	ComboboxCommandGroup,
	ComboboxCommandInput,
	ComboboxCommandItem,
	ComboboxCommandList,
	ComboboxContent,
	ComboboxTrigger,
} from "@/components/ui/combobox";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Icon } from "@/components/ui/icons";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import useDebounce from "@/hooks/use-debounce";
import { LoadingSelectState } from "./loading-select-state";

type SendNotificationFieldsProps = {
	index: number;
};

export const SendNotificationFields = ({
	index,
}: SendNotificationFieldsProps) => {
	const form = useFormContext<AutomationWizardSchema>();
	const [search, setSearch] = useState("");

	const { data: blockTypes, isLoading: isLoadingBlockTypes } = useQuery(
		buildListFilterBlockTypesQuery({
			offset: 0,
			block_schemas: {
				operator: "and_",
				block_capabilities: { all_: ["notify"] },
			},
		}),
	);

	const blockTypeSlugs = useMemo(
		() => blockTypes?.map((bt) => bt.slug) ?? [],
		[blockTypes],
	);

	const { data: blockDocuments, isLoading: isLoadingBlockDocuments } = useQuery(
		buildListFilterBlockDocumentsQuery(
			{
				block_types:
					blockTypeSlugs.length > 0
						? { slug: { any_: blockTypeSlugs } }
						: undefined,
				include_secrets: false,
				sort: "BLOCK_TYPE_AND_NAME_ASC",
				offset: 0,
			},
			{ enabled: blockTypeSlugs.length > 0 },
		),
	);

	const isLoading = isLoadingBlockTypes || isLoadingBlockDocuments;

	const groupedBlockDocuments = useMemo(() => {
		if (!blockTypes || !blockDocuments) return [];

		return blockTypes
			.map((blockType) => ({
				blockType,
				documents: blockDocuments.filter(
					(doc) => doc.block_type_id === blockType.id,
				),
			}))
			.filter((group) => group.documents.length > 0);
	}, [blockTypes, blockDocuments]);

	const filteredGroups = useMemo(() => {
		if (!search) return groupedBlockDocuments;

		const lowerSearch = search.toLowerCase();
		return groupedBlockDocuments
			.map((group) => ({
				...group,
				documents: group.documents.filter((doc) =>
					doc.name?.toLowerCase().includes(lowerSearch),
				),
			}))
			.filter((group) => group.documents.length > 0);
	}, [groupedBlockDocuments, search]);

	const getSelectedBlockDocument = useCallback(
		(blockDocumentId: string | undefined): BlockDocument | undefined => {
			if (!blockDocumentId || !blockDocuments) return undefined;
			return blockDocuments.find((doc) => doc.id === blockDocumentId);
		},
		[blockDocuments],
	);

	return (
		<div className="space-y-4">
			<FormField
				control={form.control}
				name={`actions.${index}.block_document_id`}
				render={({ field }) => {
					const selectedDoc = getSelectedBlockDocument(field.value);

					return (
						<FormItem className="flex flex-col">
							<FormLabel>Block</FormLabel>
							<Combobox>
								<ComboboxTrigger
									selected={Boolean(selectedDoc)}
									aria-label="Select notification block"
								>
									{selectedDoc
										? selectedDoc.name
										: "Select a notification block"}
								</ComboboxTrigger>
								<ComboboxContent>
									<ComboboxCommandInput
										value={search}
										onValueChange={setSearch}
										placeholder="Search for a block..."
									/>
									<ComboboxCommandEmtpy>
										No notification blocks found
									</ComboboxCommandEmtpy>
									<ComboboxCommandList>
										{isLoading ? (
											<LoadingSelectState />
										) : (
											filteredGroups.map((group) => (
												<ComboboxCommandGroup
													key={group.blockType.id}
													heading={group.blockType.name}
												>
													{group.documents.map((doc) => (
														<ComboboxCommandItem
															key={doc.id}
															value={doc.id}
															selected={field.value === doc.id}
															onSelect={field.onChange}
														>
															{doc.name}
														</ComboboxCommandItem>
													))}
												</ComboboxCommandGroup>
											))
										)}
									</ComboboxCommandList>
								</ComboboxContent>
							</Combobox>
							<FormMessage />
						</FormItem>
					);
				}}
			/>

			<TemplateField
				index={index}
				name="subject"
				label="Subject"
				placeholder="Enter notification subject..."
			/>

			<TemplateField
				index={index}
				name="body"
				label="Body"
				placeholder="Enter notification body..."
				multiline
			/>

			<div className="flex items-start gap-2 rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-200">
				<Icon id="Info" className="mt-0.5 size-4 shrink-0" />
				<p>
					In addition to any fields present on the triggering event, the
					following objects can be used in notification templates:{" "}
					<code className="rounded bg-blue-100 px-1 py-0.5 font-mono text-xs dark:bg-blue-900">
						flow
					</code>
					,{" "}
					<code className="rounded bg-blue-100 px-1 py-0.5 font-mono text-xs dark:bg-blue-900">
						deployment
					</code>
					,{" "}
					<code className="rounded bg-blue-100 px-1 py-0.5 font-mono text-xs dark:bg-blue-900">
						flow_run
					</code>
					,{" "}
					<code className="rounded bg-blue-100 px-1 py-0.5 font-mono text-xs dark:bg-blue-900">
						work_pool
					</code>
					,{" "}
					<code className="rounded bg-blue-100 px-1 py-0.5 font-mono text-xs dark:bg-blue-900">
						work_queue
					</code>
					, and{" "}
					<code className="rounded bg-blue-100 px-1 py-0.5 font-mono text-xs dark:bg-blue-900">
						metric
					</code>
					.
				</p>
			</div>
		</div>
	);
};

type TemplateFieldProps = {
	index: number;
	name: "subject" | "body";
	label: string;
	placeholder?: string;
	multiline?: boolean;
};

const TemplateField = ({
	index,
	name,
	label,
	placeholder,
	multiline = false,
}: TemplateFieldProps) => {
	const form = useFormContext<AutomationWizardSchema>();
	const { validateTemplate } = useValidateTemplate();
	const [validationError, setValidationError] = useState<string | null>(null);
	const [isValidating, setIsValidating] = useState(false);

	const fieldValue = form.watch(`actions.${index}.${name}`);
	const debouncedValue = useDebounce(fieldValue, 1000);

	useEffect(() => {
		const validate = async () => {
			if (!debouncedValue || debouncedValue.trim() === "") {
				setValidationError(null);
				return;
			}

			setIsValidating(true);
			try {
				const result = await validateTemplate(debouncedValue);
				if (result.valid) {
					setValidationError(null);
				} else {
					setValidationError(result.error);
				}
			} catch {
				setValidationError(null);
			} finally {
				setIsValidating(false);
			}
		};

		void validate();
	}, [debouncedValue, validateTemplate]);

	const InputComponent = multiline ? Textarea : Input;

	return (
		<FormField
			control={form.control}
			name={`actions.${index}.${name}`}
			render={({ field }) => (
				<FormItem>
					<FormLabel className="flex items-center gap-2">
						{label}
						{isValidating && (
							<Icon id="Loader2" className="size-3 animate-spin" />
						)}
					</FormLabel>
					<FormControl>
						<InputComponent
							{...field}
							value={field.value ?? ""}
							placeholder={placeholder}
							className={validationError ? "border-destructive" : ""}
						/>
					</FormControl>
					{validationError && (
						<p className="text-sm text-destructive">{validationError}</p>
					)}
					<FormMessage />
				</FormItem>
			)}
		/>
	);
};
