import type { FormEvent } from 'react'
import { QuickChips } from './QuickChips'

type InputBarProps = {
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  onChipClick: (text: string) => void
}

function SendIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
    </svg>
  )
}

export function InputBar({
  value,
  onChange,
  onSubmit,
  onChipClick,
}: InputBarProps) {
  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    onSubmit()
  }

  return (
    <div className="sticky bottom-0 shrink-0">
      <div
        className="pointer-events-none h-10 bg-gradient-to-b from-transparent to-[#0f0e0c]"
        aria-hidden
      />
      <div className="pointer-events-auto px-4 pb-5">
        <form onSubmit={handleSubmit} className="mx-auto max-w-[720px]">
          <div className="relative rounded-2xl bg-white/[0.03] p-2 ring-1 ring-white/10 shadow-[0_20px_60px_rgba(0,0,0,0.45)] backdrop-blur">
            <input
              type="text"
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder="How can I help with this ticket?"
              className="w-full rounded-xl bg-transparent py-3 pl-3 pr-12 text-sm font-normal text-[#e8e3dc] placeholder:text-[#6b6560] outline-none focus:ring-2 focus:ring-[#7c3aed]/60 focus:ring-offset-0"
              aria-label="Ticket message"
            />
            <button
              type="submit"
              className="absolute right-3 top-1/2 flex h-9 w-9 -translate-y-1/2 cursor-pointer items-center justify-center rounded-xl bg-[#7c3aed] text-white shadow-[0_12px_30px_rgba(124,58,237,0.25)] transition-colors hover:bg-[#6d28d9]"
              aria-label="Send"
            >
              <SendIcon />
            </button>
          </div>
          <QuickChips onChipClick={onChipClick} />
          <p className="mt-2 text-[11px] font-normal text-[#6b6560]">
            Stripe IDs optional
          </p>
        </form>
      </div>
    </div>
  )
}
