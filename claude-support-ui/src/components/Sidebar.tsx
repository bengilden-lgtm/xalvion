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
  indent?: boolean
  smaller?: boolean
}

const NAV: NavItem[] = [
  { id: 'workspace', symbol: '◇', label: 'Workspace' },
  { id: 'access', symbol: '−', label: 'Access' },
  { id: 'plans', symbol: '◆', label: 'Plans', indent: true, smaller: true },
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
    <aside className="flex h-full w-16 shrink-0 flex-col bg-[#1f1c18] md:w-[265px]">
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-3 pb-6 pt-5 md:px-3">
        {/* Brand */}
        <div className="flex items-center justify-center gap-3 md:justify-start">
          <div
            className="h-9 w-9 shrink-0 rounded-md bg-[#2a2520] ring-1 ring-[#3a3530]"
            aria-hidden
          />
          <span className="hidden text-[15px] font-medium text-[#e8e3dc] md:inline">
            Claude Desk
          </span>
        </div>

        {/* Mode badges */}
        <div className="mt-4 hidden flex-col gap-2 md:flex">
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center rounded-full bg-[#7c3aed] px-3 py-1 text-xs font-medium text-white">
              Live run
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[#3a3530] px-3 py-1 text-xs font-normal text-[#9c9189]">
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#6b6560]"
                aria-hidden
              />
              Preview mode · 1 run remaining
            </span>
          </div>
        </div>
        <div className="mt-3 flex justify-center md:hidden">
          <span
            className="h-2 w-2 rounded-full bg-[#7c3aed]"
            title="Live run"
            aria-label="Live run"
          />
        </div>

        <p className="mt-6 hidden text-[10px] font-medium uppercase tracking-wider text-[#6b6560] md:block">
          NAVIGATE
        </p>

        <nav className="mt-3 flex flex-col gap-0.5" aria-label="Primary">
          {NAV.map((item) => {
            const active = activeNav === item.id
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavChange(item.id)}
                className={[
                  'flex h-[38px] w-full items-center rounded-md pl-3 text-left text-sm font-medium transition-colors',
                  item.indent ? 'md:ml-2 md:text-[13px]' : '',
                  active
                    ? 'border-l-[3px] border-l-[#7c3aed] bg-[#2d2820] text-[#e8e3dc]'
                    : 'border-l-[3px] border-l-transparent text-[#9c9189] hover:bg-[#252118] hover:text-[#e8e3dc]',
                  item.smaller ? 'md:text-[13px]' : '',
                  'justify-center md:justify-start',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                <span className="inline-flex min-w-[1.25rem] justify-center md:justify-start">
                  {item.symbol}
                </span>
                <span className="hidden md:inline md:ml-1.5">{item.label}</span>
              </button>
            )
          })}
        </nav>

        <div className="mt-auto hidden flex-col pt-8 md:flex">
          <p className="text-[10px] font-medium uppercase tracking-wider text-[#6b6560]">
            ACCOUNT / ACCESS
          </p>
          <p className="mt-1 text-xs font-normal leading-snug text-[#6b6560]">
            Sign in to sync workspace settings and operator approvals.
          </p>
          <label className="mt-4 block">
            <span className="sr-only">Username</span>
            <input
              type="text"
              placeholder="Username"
              className="w-full rounded-md border border-[#3a3530] bg-[#2a2520] px-3 py-2 text-xs font-normal text-[#e8e3dc] placeholder:text-[#6b6560] outline-none focus:ring-2 focus:ring-[#7c3aed]"
            />
          </label>
          <label className="mt-2 block">
            <span className="sr-only">Password</span>
            <input
              type="password"
              placeholder="Password"
              className="w-full rounded-md border border-[#3a3530] bg-[#2a2520] px-3 py-2 text-xs font-normal text-[#e8e3dc] placeholder:text-[#6b6560] outline-none focus:ring-2 focus:ring-[#7c3aed]"
            />
          </label>
        </div>
      </div>
    </aside>
  )
}
