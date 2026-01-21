import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type SchemaFormInputStringFormatPasswordProps = {
	value: string | undefined;
	onValueChange: (value: string | undefined) => void;
	id: string;
};

export function SchemaFormInputStringFormatPassword({
	value,
	onValueChange,
	id,
}: SchemaFormInputStringFormatPasswordProps) {
	const [showPassword, setShowPassword] = useState(false);

	const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		onValueChange(e.target.value || undefined);
	};

	return (
		<div className="relative">
			<Input
				id={id}
				type={showPassword ? "text" : "password"}
				value={value ?? ""}
				onChange={handleChange}
				autoComplete="off"
				className="pr-10"
			/>
			<Button
				type="button"
				variant="ghost"
				size="icon"
				className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
				onClick={() => setShowPassword(!showPassword)}
				aria-label={showPassword ? "Hide password" : "Show password"}
			>
				{showPassword ? (
					<EyeOff className="h-4 w-4" />
				) : (
					<Eye className="h-4 w-4" />
				)}
			</Button>
		</div>
	);
}
