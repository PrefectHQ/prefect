import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";

type KeyValueProps = {
	label: string;
	value: React.ReactNode;
	copyable?: boolean;
	copyValue?: string;
};

export function KeyValue({ label, value, copyable, copyValue }: KeyValueProps) {
	const handleCopy = () => {
		const textToCopy = copyValue ?? (typeof value === "string" ? value : "");
		void navigator.clipboard.writeText(textToCopy);
		toast.success(`${label} copied`);
	};

	return (
		<dl className="flex flex-col gap-1">
			<dt className="text-muted-foreground text-sm">{label}</dt>
			<dd className="text-sm flex items-center gap-2">
				{value}
				{copyable && (
					<Button variant="ghost" size="icon" onClick={handleCopy}>
						<Icon id="Copy" className="size-4" />
					</Button>
				)}
			</dd>
		</dl>
	);
}
