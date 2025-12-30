import type { ReactNode } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type FormMode = "Form" | "JSON";

type FormModeToggleProps = {
	defaultValue?: FormMode;
	formContent: ReactNode;
	jsonContent: ReactNode;
};

export const FormModeToggle = ({
	defaultValue = "Form",
	formContent,
	jsonContent,
}: FormModeToggleProps) => {
	return (
		<Tabs defaultValue={defaultValue}>
			<TabsList>
				<TabsTrigger value="Form">Form</TabsTrigger>
				<TabsTrigger value="JSON">JSON</TabsTrigger>
			</TabsList>
			<TabsContent value="Form">{formContent}</TabsContent>
			<TabsContent value="JSON">{jsonContent}</TabsContent>
		</Tabs>
	);
};
