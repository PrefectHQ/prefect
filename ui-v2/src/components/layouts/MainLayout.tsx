import { AppSidebar } from "@/components/ui/app-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { Toaster } from "@/components/ui/sonner";

export function MainLayout({ children }: { children: React.ReactNode }) {
	return (
		<SidebarProvider className="h-full">
			<AppSidebar />
			<main className="p-4 pb-0 max-h-full h-full w-full">{children}</main>
			<Toaster />
		</SidebarProvider>
	);
}
