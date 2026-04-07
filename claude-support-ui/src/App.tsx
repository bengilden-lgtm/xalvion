import { useCallback, useState } from 'react'
import { MainPanel } from './components/MainPanel'
import { Sidebar, type NavId } from './components/Sidebar'

function buildMockResponse(userMessage: string): string {
  const trimmed = userMessage.trim()
  if (!trimmed) {
    return ''
  }
  return `Hi there — thanks for reaching out. I've reviewed your note: "${trimmed.slice(0, 120)}${trimmed.length > 120 ? '…' : ''}"

We're issuing a courtesy credit to your account today. You'll see it on your next statement within 3–5 business days. If anything still looks off, reply here and we'll escalate with our billing team.

Thanks for your patience, and we're sorry for the trouble.`
}

export default function App() {
  const [activeNav, setActiveNav] = useState<NavId>('access')
  const [inputValue, setInputValue] = useState('')
  const [activeTicket, setActiveTicket] = useState<{
    response: string
  } | null>(null)

  const handleSubmit = useCallback(() => {
    const q = inputValue.trim()
    if (!q) return
    setActiveTicket({
      response: buildMockResponse(q),
    })
  }, [inputValue])

  const handleChipClick = useCallback((text: string) => {
    setInputValue(text)
  }, [])

  return (
    <div className="flex h-full min-h-0 flex-row bg-gradient-to-b from-[#171613] via-[#141311] to-[#0f0e0c]">
      <Sidebar activeNav={activeNav} onNavChange={setActiveNav} />
      <MainPanel
        inputValue={inputValue}
        onInputChange={setInputValue}
        onSubmit={handleSubmit}
        onChipClick={handleChipClick}
        activeTicket={activeTicket}
      />
    </div>
  )
}
