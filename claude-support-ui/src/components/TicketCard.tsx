import { ApprovalBlock } from './ApprovalBlock'

type TicketCardProps = {
  responseText: string
}

export function TicketCard({ responseText }: TicketCardProps) {
  return (
    <div className="rounded-xl border border-[#3a3530] bg-[#252118] p-5">
      <div className="text-[15px] font-normal leading-[1.6] text-[#d4cec7] whitespace-pre-wrap">
        {responseText}
      </div>
      <ApprovalBlock responseText={responseText} />
    </div>
  )
}
