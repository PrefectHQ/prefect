import type { ReactNode } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export type FormMode = "Form" | "JSON";

type FormModeToggleProps = {
	defaultValue?: FormMode;
	/** Controlled value - when provided, the component becomes controlled */
	value?: FormMode;
	/** Callback when the mode changes - required for controlled mode */
	onValueChange?: (value: FormMode) => void;
	formContent: ReactNode;
	jsonContent: ReactNode;
};

export const FormModeToggle = ({
	defaultValue = "Form",
	value,
	onValueChange,
	formContent,
	jsonContent,
}: FormModeToggleProps) => {
	// When value is provided, use controlled mode; otherwise use uncontrolled mode
	const tabsProps =
		value !== undefined
			? { value, onValueChange: onValueChange as (value: string) => void }
			: { defaultValue };

	return (
		<Tabs {...tabsProps}>
			<div className="flex justify-center">
				<TabsList>
					<TabsTrigger value="Form">Form</TabsTrigger>
					<TabsTrigger value="JSON">JSON</TabsTrigger>
				</TabsList>
			</div>
			<TabsContent value="Form">{formContent}</TabsContent>
			<TabsContent value="JSON">{jsonContent}</TabsContent>
		</Tabs>
	);
};
