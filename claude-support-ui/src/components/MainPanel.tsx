import { TicketCard } from './TicketCard'
import { InputBar } from './InputBar'

function greetingPhrase() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

type MainPanelProps = {
  inputValue: string
  onInputChange: (v: string) => void
  onSubmit: () => void
  onChipClick: (text: string) => void
  activeTicket: { response: string } | null
}

export function MainPanel({
  inputValue,
  onInputChange,
  onSubmit,
  onChipClick,
  activeTicket,
}: MainPanelProps) {
  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <main className="min-h-0 flex-1">
        <div className="mx-auto max-w-[740px] px-6 pb-10 pt-10">
          <header className="text-center">
            <h1 className="text-[28px] font-semibold leading-tight text-[#e8e3dc]">
              Paste a support ticket
            </h1>
            <div className="mt-2 flex flex-wrap items-center justify-center gap-2 text-[12px] font-normal text-[#9c9189]">
              <span>Get a customer-ready reply instantly</span>
              <span className="text-[#6b6560]" aria-hidden>
                ·
              </span>
              <span>Sensitive actions stay gated for approval</span>
            </div>
          </header>

          {!activeTicket ? (
            <section className="mt-14 flex min-h-[calc(100vh-360px)] flex-col items-center justify-center text-center">
              <p className="text-2xl font-normal text-[#e8e3dc]">
                {greetingPhrase()}
              </p>
              <p className="mt-2 text-base font-normal text-[#9c9189]">
                What ticket should we work through?
              </p>
              <p className="mt-4 text-[13px] font-normal text-[#6b6560]">
                Preview mode · 1 operator run remaining
              </p>
            </section>
          ) : (
            <section className="mt-8">
              <TicketCard responseText={activeTicket.response} />
            </section>
          )}
        </div>
      </main>

      <InputBar
        value={inputValue}
        onChange={onInputChange}
        onSubmit={onSubmit}
        onChipClick={onChipClick}
      />
    </div>
  )
}
