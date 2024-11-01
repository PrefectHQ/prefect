
import { ScrollArea } from "@/components/ui/scroll-area"
import { NavItem } from "@/components/ui/sidebar"
import { Workflow } from "lucide-react"

export function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col h-screen">
      <header>
      <nav className="border-border border-b h-14"></nav>
      </header>
        <div className="flex flex-1 overflow-hidden flex-row">
        <aside className="flex-shrink-0 w-64 border-border border-r">
          <div className="flex flex-col w-64 border-r bg-background h-screen">
            <ScrollArea className="flex-1">
              <nav className="space-y-2 p-2">
                <NavItem to="/flows" icon={<Workflow className="mr-2 h-4 w-4" />} activeOptions={{ exact: true }}>
                  Flows
                </NavItem>
              </nav>
            </ScrollArea>
          </div>
        </aside>
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  )
}