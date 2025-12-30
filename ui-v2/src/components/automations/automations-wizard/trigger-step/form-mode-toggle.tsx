import type { ReactNode } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type FormMode = "Form" | "JSON";

type FormModeToggleProps = {
	value: FormMode;
	onValueChange: (mode: FormMode) => void;
	formContent: ReactNode;
	jsonContent: ReactNode;
};

export const FormModeToggle = ({
	value,
	onValueChange,
	formContent,
	jsonContent,
}: FormModeToggleProps) => {
	const handleValueChange = (newValue: string) => {
		onValueChange(newValue as FormMode);
	};

	return (
		<Tabs value={value} onValueChange={handleValueChange}>
			<TabsList>
				<TabsTrigger value="Form">Form</TabsTrigger>
				<TabsTrigger value="JSON">JSON</TabsTrigger>
			</TabsList>
			<TabsContent value="Form">{formContent}</TabsContent>
			<TabsContent value="JSON">{jsonContent}</TabsContent>
		</Tabs>
	);
};
