import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { WorkPoolFormValues } from "./types";

interface InformationStepProps {
	values: WorkPoolFormValues;
	onChange: (values: Partial<WorkPoolFormValues>) => void;
}

export const InformationStep = ({ values, onChange }: InformationStepProps) => {
	return (
		<div className="space-y-6">
			<div className="space-y-2">
				<Label htmlFor="name">Name</Label>
				<Input
					id="name"
					value={values.name || ""}
					onChange={(e) => onChange({ name: e.target.value })}
				/>
			</div>

			<div className="space-y-2">
				<Label htmlFor="description">Description (Optional)</Label>
				<Textarea
					id="description"
					value={values.description || ""}
					onChange={(e) => onChange({ description: e.target.value })}
					rows={7}
				/>
			</div>

			<div className="space-y-2">
				<Label htmlFor="concurrencyLimit">
					Flow Run Concurrency (Optional)
				</Label>
				<Input
					id="concurrencyLimit"
					type="number"
					min="0"
					value={values.concurrencyLimit || ""}
					onChange={(e) => {
						const value = e.target.value;
						onChange({
							concurrencyLimit:
								value === "" ? null : Number.parseInt(value, 10),
						});
					}}
					placeholder="Unlimited"
				/>
			</div>
		</div>
	);
};
