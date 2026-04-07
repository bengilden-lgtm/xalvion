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
    <div className="shrink-0 border-t border-[#3a3530] bg-[#1f1c18] px-6 py-4">
      <form onSubmit={handleSubmit} className="mx-auto max-w-[680px]">
        <div className="relative">
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="How can I help with this ticket?"
            className="w-full rounded-xl border border-[#3a3530] bg-[#2a2520] py-[14px] pl-4 pr-[50px] text-sm font-normal text-[#e8e3dc] placeholder:text-[#6b6560] outline-none focus:ring-2 focus:ring-[#7c3aed] focus:ring-offset-0"
            aria-label="Ticket message"
          />
          <button
            type="submit"
            className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 cursor-pointer items-center justify-center rounded-full bg-[#7c3aed] text-white transition-colors hover:bg-[#6d28d9]"
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
  )
}
