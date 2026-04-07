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
          className="cursor-pointer rounded-full bg-white/[0.03] px-[14px] py-[6px] text-[13px] font-normal text-[#9c9189] ring-1 ring-white/10 transition-colors hover:bg-white/[0.06] hover:text-[#e8e3dc] hover:ring-[#7c3aed]/40"
        >
          {label}
        </button>
      ))}
    </div>
  )
}
