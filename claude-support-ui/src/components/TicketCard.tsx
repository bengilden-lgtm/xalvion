import { ApprovalBlock } from './ApprovalBlock'

type TicketCardProps = {
  responseText: string
}

export function TicketCard({ responseText }: TicketCardProps) {
  return (
    <div className="mt-10">
      <div className="whitespace-pre-wrap text-[15px] font-normal leading-[1.7] text-[#d4cec7]">
        {responseText}
      </div>
      <ApprovalBlock responseText={responseText} />
    </div>
  )
}
