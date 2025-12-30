import { Button } from "@/components/ui/button";

type FormMode = "Form" | "JSON";

type FormModeToggleProps = {
	value: FormMode;
	onValueChange: (mode: FormMode) => void;
};

export const FormModeToggle = ({
	value,
	onValueChange,
}: FormModeToggleProps) => {
	return (
		<div className="flex gap-1">
			<Button
				variant={value === "Form" ? "default" : "outline"}
				size="sm"
				onClick={() => onValueChange("Form")}
			>
				Form
			</Button>
			<Button
				variant={value === "JSON" ? "default" : "outline"}
				size="sm"
				onClick={() => onValueChange("JSON")}
			>
				JSON
			</Button>
		</div>
	);
};
