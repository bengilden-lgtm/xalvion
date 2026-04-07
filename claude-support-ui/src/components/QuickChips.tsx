const CHIPS = [
  'Duplicate charge',
  'Late package',
  'Damaged order',
  'Where is my order',
] as const

type QuickChipsProps = {
  onChipClick: (text: string) => void
}

export function QuickChips({ onChipClick }: QuickChipsProps) {
  return (
    <div className="mt-3 flex flex-row flex-wrap gap-2">
      {CHIPS.map((label) => (
        <button
          key={label}
          type="button"
          onClick={() => onChipClick(label)}
          className="cursor-pointer rounded-full border border-[#3a3530] bg-[#2a2520] px-[14px] py-[6px] text-[13px] font-normal text-[#9c9189] transition-colors hover:border-[#7c3aed] hover:text-[#e8e3dc]"
        >
          {label}
        </button>
      ))}
    </div>
  )
}
