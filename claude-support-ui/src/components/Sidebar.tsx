export type NavId =
  | 'workspace'
  | 'access'
  | 'plans'
  | 'integrations'
  | 'crm'
  | 'revenue'
  | 'more'

type NavItem = {
  id: NavId
  symbol: string
  label: string
}

const NAV: NavItem[] = [
  { id: 'workspace', symbol: '◇', label: 'Workspace' },
  { id: 'access', symbol: '−', label: 'Access' },
  { id: 'plans', symbol: '◆', label: 'Plans' },
  { id: 'integrations', symbol: '⊞', label: 'Integrations' },
  { id: 'crm', symbol: '◎', label: 'CRM' },
  { id: 'revenue', symbol: '◎', label: 'Revenue' },
  { id: 'more', symbol: '···', label: 'More' },
]

type SidebarProps = {
  activeNav: NavId
  onNavChange: (id: NavId) => void
}

export function Sidebar({ activeNav, onNavChange }: SidebarProps) {
  return (
    <aside className="flex h-full w-[68px] shrink-0 flex-col border-r border-white/5 bg-[#141311]">
      <div className="flex min-h-0 flex-1 flex-col items-center overflow-y-auto px-2 pb-4 pt-3">
        <button
          type="button"
          onClick={() => onNavChange('workspace')}
          className="group relative flex h-10 w-10 items-center justify-center rounded-xl bg-white/[0.03] text-[#e8e3dc] ring-1 ring-white/5 transition-colors hover:bg-white/[0.06]"
          aria-label="Workspace"
          title="Workspace"
        >
          <span className="text-sm">X</span>
        </button>

        <nav className="mt-6 flex w-full flex-col items-center gap-2" aria-label="Primary">
          {NAV.map((item) => {
            const active = activeNav === item.id
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavChange(item.id)}
                className={[
                  'group relative flex h-10 w-10 items-center justify-center rounded-xl text-sm font-medium transition-colors',
                  active
                    ? 'bg-white/[0.06] text-[#e8e3dc] ring-1 ring-white/10'
                    : 'text-[#9c9189] hover:bg-white/[0.05] hover:text-[#e8e3dc]',
                ]
                  .filter(Boolean)
                  .join(' ')}
                aria-label={item.label}
                title={item.label}
              >
                <span className="inline-flex min-w-[1.25rem] justify-center">
                  {item.symbol}
                </span>
              </button>
            )
          })}
        </nav>
      </div>
    </aside>
  )
}
