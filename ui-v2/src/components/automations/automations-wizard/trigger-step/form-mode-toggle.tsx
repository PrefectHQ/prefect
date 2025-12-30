import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

type FormMode = "Form" | "JSON";

type FormModeToggleProps = {
	value: FormMode;
	onValueChange: (mode: FormMode) => void;
};

export const FormModeToggle = ({
	value,
	onValueChange,
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
		</Tabs>
	);
};
