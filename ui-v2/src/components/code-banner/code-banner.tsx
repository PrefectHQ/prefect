import { Copy, Terminal } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface CodeBannerProps {
	command: string;
	title: string;
	subtitle: string;
	className?: string;
}

export const CodeBanner = ({
	command,
	title,
	subtitle,
	className,
}: CodeBannerProps) => {
	const [copying, setCopying] = useState(false);

	const handleCopy = async () => {
		if (copying) return;

		setCopying(true);
		try {
			await navigator.clipboard.writeText(command);
			toast.success("Command copied to clipboard");
		} catch (_error) {
			toast.error("Failed to copy command");
		} finally {
			setCopying(false);
		}
	};

	return (
		<Alert
			className={cn("bg-slate-900 text-slate-100 border-slate-700", className)}
		>
			<Terminal className="h-4 w-4" />
			<div className="flex flex-col space-y-3">
				<div>
					<AlertTitle className="text-slate-100">{title}</AlertTitle>
					<AlertDescription className="text-slate-300">
						{subtitle}
					</AlertDescription>
				</div>
				<div className="flex items-center justify-between bg-slate-800 border border-slate-600 rounded-md p-3">
					<code className="font-mono text-sm text-slate-100 select-all">
						{command}
					</code>
					<Button
						variant="ghost"
						size="sm"
						onClick={handleCopy}
						disabled={copying}
						className="ml-2 text-slate-300 hover:text-slate-100 hover:bg-slate-700"
					>
						<Copy className="h-4 w-4" />
					</Button>
				</div>
			</div>
		</Alert>
	);
};
