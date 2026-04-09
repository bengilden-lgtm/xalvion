import { useState } from 'react'

function CopyIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect
        x="9"
        y="9"
        width="11"
        height="11"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M6 15H5a2 2 0 01-2-2V5a2 2 0 012-2h8a2 2 0 012 2v1"
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  )
}

type ApprovalBlockProps = {
  responseText: string
}

export function ApprovalBlock({ responseText }: ApprovalBlockProps) {
  const [whyOpen, setWhyOpen] = useState(false)
  const [action, setAction] = useState<'pending' | 'rejected' | 'approved'>(
    'pending',
  )

  async function copyResponse() {
    try {
      await navigator.clipboard.writeText(responseText)
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="mt-6 pt-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#4c1d95]/40 px-2.5 py-1 text-xs font-medium text-[#c4b5fd] ring-1 ring-[#a78bfa]/20">
          <span aria-hidden>⚡</span>
          Approval required
        </span>
        <div className="ml-auto flex items-center gap-2">
          {action === 'pending' && (
            <>
              <button
                type="button"
                onClick={() => setAction('rejected')}
                className="cursor-pointer rounded-lg bg-[#7f1d1d]/50 px-3 py-1.5 text-sm font-medium text-[#fecaca] ring-1 ring-[#7f1d1d]/50 transition-colors hover:bg-[#7f1d1d]/65"
              >
                Reject
              </button>
              <button
                type="button"
                onClick={() => setAction('approved')}
                className="cursor-pointer rounded-lg bg-[#7c3aed] px-3 py-1.5 text-sm font-medium text-white shadow-[0_10px_30px_rgba(124,58,237,0.18)] transition-colors hover:bg-[#6d28d9]"
              >
                Approve
              </button>
            </>
          )}
          {action === 'rejected' && (
            <span className="rounded-lg bg-[#7f1d1d]/55 px-3 py-1.5 text-sm font-medium text-[#fecaca] ring-1 ring-[#7f1d1d]/50">
              Rejected
            </span>
          )}
          {action === 'approved' && (
            <span className="rounded-lg bg-[#7c3aed] px-3 py-1.5 text-sm font-medium text-white shadow-[0_10px_30px_rgba(124,58,237,0.16)]">
              Approved
            </span>
          )}
        </div>
      </div>
      <p className="mt-3 text-[13px] font-normal italic text-[#9c9189]">
        Draft held for approval. Nothing sent to the customer.
      </p>
      <div className="mt-2 flex items-center gap-3">
        <button
          type="button"
          onClick={() => setWhyOpen((o) => !o)}
          className="cursor-pointer text-sm font-normal text-[#a78bfa] hover:underline"
          aria-expanded={whyOpen}
        >
          Why this decision {whyOpen ? '▴' : '▾'}
        </button>
        <button
          type="button"
          onClick={copyResponse}
          className="cursor-pointer rounded-md p-1.5 text-[#6b6560] transition-colors hover:bg-white/[0.05] hover:text-[#9c9189]"
          aria-label="Copy response"
        >
          <CopyIcon />
        </button>
      </div>
      {whyOpen && (
        <p className="mt-2 text-[13px] leading-relaxed text-[#9c9189]">
          This reply includes a policy-sensitive action (for example, a refund above your approval
          threshold). Approve to release the draft, or reject to route the case for manual follow-up.
        </p>
      )}
      <div className="mt-6 h-px w-full bg-white/5" aria-hidden />
      <p className="mt-3 text-[12px] font-normal text-[#6b6560]">
        Preview · no customer message sent
      </p>
    </div>
  )
}
