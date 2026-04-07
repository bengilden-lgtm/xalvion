import React, { useMemo, useState } from "react";

function LeftRail({ active = "chats" }) {
  const items = useMemo(
    () => [
      { id: "new", label: "New", glyph: "+" },
      { id: "search", label: "Search", glyph: "⌕" },
      { id: "library", label: "Library", glyph: "▦" },
      { id: "settings", label: "Settings", glyph: "⚙" },
      { id: "code", label: "Code", glyph: "</>" },
    ],
    []
  );

  return (
    <div className="w-[56px] shrink-0 bg-[#171716] border-r border-[#232321] flex flex-col items-center py-[14px]">
      <div className="w-[30px] h-[30px] rounded-full bg-[#7a5cff] opacity-80 mb-[16px]" />
      <div className="flex flex-col gap-[10px]">
        {items.map((it) => (
          <button
            key={it.id}
            type="button"
            className={[
              "w-[34px] h-[34px] rounded-[10px] flex items-center justify-center text-[12px] border",
              it.id === active
                ? "bg-[#20201e] border-[#2c2c29] text-[#e9e7e2]"
                : "bg-transparent border-transparent text-[#9b9891] hover:bg-[#1c1c1a] hover:border-[#262624] transition-opacity",
            ].join(" ")}
            aria-label={it.label}
          >
            <span className="leading-none">{it.glyph}</span>
          </button>
        ))}
      </div>

      <div className="mt-auto w-full flex flex-col items-center gap-[10px] pb-[10px]">
        <div className="w-[34px] h-[34px] rounded-full bg-[#232321] border border-[#2c2c29]" />
        <div className="w-[34px] h-[34px] rounded-full bg-[#232321] border border-[#2c2c29] flex items-center justify-center text-[12px] text-[#c9c6bf]">
          BR
        </div>
      </div>
    </div>
  );
}

function Sidebar({ chats, activeChatId, onSelectChat }) {
  return (
    <div className="w-[280px] shrink-0 bg-[#1a1a19] border-r border-[#232321] flex flex-col">
      <div className="px-[14px] pt-[14px] pb-[10px]">
        <div className="h-[36px] rounded-[12px] bg-[#20201e] border border-[#2c2c29] flex items-center px-[12px] text-[#c9c6bf] text-[13px]">
          <span className="opacity-70">Search</span>
        </div>
      </div>

      <div className="px-[14px] pb-[10px]">
        <p className="text-[#8f8c85] text-[11px] font-semibold tracking-[0.08em] m-0">
          RECENT
        </p>
      </div>

      <div className="px-[8px] flex-1 overflow-y-auto">
        {chats.map((c) => {
          const active = c.id === activeChatId;
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => onSelectChat(c.id)}
              className={[
                "w-full text-left px-[10px] py-[10px] rounded-[12px] border mb-[6px]",
                active
                  ? "bg-[#20201e] border-[#2c2c29] text-[#e9e7e2]"
                  : "bg-transparent border-transparent text-[#b8b5ad] hover:bg-[#1f1f1d] hover:border-[#272725] transition-opacity",
              ].join(" ")}
            >
              <div className="text-[13px] leading-tight">{c.title}</div>
              <div className="text-[11px] text-[#8f8c85] mt-[3px]">
                {c.preview}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ChatMain({ chat, onSend }) {
  const [draft, setDraft] = useState("");

  const showGreeting = chat.messages.length === 0;

  const quickPills = useMemo(
    () => ["Write", "Learn", "Code", "Life stuff", "Claude's choice"],
    []
  );

  function send() {
    const text = draft.trim();
    if (!text) return;
    onSend(text);
    setDraft("");
  }

  return (
    <div className="flex-1 bg-[#1b1b1a] flex flex-col relative">
      <div className="h-[54px] border-b border-[#232321] flex items-center px-[18px]">
        <div className="flex items-center gap-[10px] text-[#cfccc4]">
          <span className="text-[13px] font-semibold">{chat.title}</span>
          <span className="text-[#8f8c85] text-[12px]">▾</span>
        </div>
        <div className="ml-auto">
          <button
            type="button"
            className="h-[30px] px-[12px] rounded-[999px] bg-[#20201e] border border-[#2c2c29] text-[#cfccc4] text-[12px]"
          >
            Share
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {showGreeting ? (
          <div className="min-h-[520px] flex items-center justify-center">
            <div className="text-center">
              <div className="flex items-center justify-center gap-[10px] mb-[14px]">
                <div className="w-[18px] h-[18px] rounded-full bg-[#ff7a50] opacity-90" />
                <h1 className="text-[#d7d3cb] text-[44px] font-[500] tracking-[-0.02em] m-0">
                  Evening, Ben
                </h1>
              </div>

              <div className="w-[640px] max-w-[calc(100vw-120px)] mx-auto">
                <div className="rounded-[18px] bg-[#20201e] border border-[#2c2c29] px-[18px] py-[16px] text-left">
                  <div className="text-[#9c9992] text-[14px] mb-[10px]">
                    How can I help you today?
                  </div>
                  <div className="flex items-center justify-between text-[#8f8c85] text-[12px]">
                    <div className="flex items-center gap-[10px]">
                      <div className="w-[28px] h-[28px] rounded-[10px] border border-[#2c2c29] flex items-center justify-center">
                        +
                      </div>
                    </div>
                    <div className="flex items-center gap-[10px]">
                      <div className="flex items-center gap-[6px]">
                        <span>Sonnet 4.6 Extended</span>
                        <span>▾</span>
                      </div>
                      <div className="w-[28px] h-[28px] rounded-[10px] border border-[#2c2c29] flex items-center justify-center">
                        〣
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex gap-[10px] justify-center mt-[14px]">
                  {quickPills.map((p) => (
                    <button
                      key={p}
                      type="button"
                      className="h-[28px] px-[12px] rounded-[999px] bg-[#1f1f1d] border border-[#2a2a28] text-[#bdbab2] text-[12px]"
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="px-[22px] py-[22px]">
            <div className="max-w-[860px] mx-auto">
              {chat.messages.map((m) => (
                <div
                  key={m.id}
                  className={[
                    "w-full flex mb-[16px]",
                    m.role === "user" ? "justify-end" : "justify-start",
                  ].join(" ")}
                >
                  <div
                    className={[
                      "max-w-[520px] rounded-[18px] px-[14px] py-[10px] text-[14px] leading-[1.5] border",
                      m.role === "user"
                        ? "bg-[#232321] border-[#2c2c29] text-[#e9e7e2]"
                        : "bg-transparent border-[#2c2c29] text-[#d7d3cb]",
                    ].join(" ")}
                  >
                    {m.text}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="sticky bottom-0 bg-[#1b1b1a] pb-[18px]">
        <div className="max-w-[920px] mx-auto px-[22px]">
          <div className="rounded-[18px] bg-[#20201e] border border-[#2c2c29]">
            <div className="flex items-center gap-[10px] px-[14px] py-[12px]">
              <button
                type="button"
                className="w-[34px] h-[34px] rounded-[12px] border border-[#2c2c29] text-[#cfccc4] flex items-center justify-center"
              >
                +
              </button>
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") send();
                }}
                placeholder="Reply..."
                className="flex-1 bg-transparent outline-none text-[#e9e7e2] placeholder:text-[#8f8c85] text-[14px]"
              />
              <div className="flex items-center gap-[10px] text-[#8f8c85] text-[12px]">
                <div className="flex items-center gap-[6px]">
                  <span>Sonnet 4.6 Extended</span>
                  <span>▾</span>
                </div>
                <button
                  type="button"
                  onClick={send}
                  className="w-[34px] h-[34px] rounded-[12px] border border-[#2c2c29] text-[#cfccc4] flex items-center justify-center"
                  aria-label="Send"
                >
                  〣
                </button>
              </div>
            </div>
          </div>

          <p className="text-center text-[#6f6d67] text-[11px] mt-[10px] mb-0">
            Claude is AI and can make mistakes. Please double-check responses.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [chats, setChats] = useState(() => [
    {
      id: "greeting",
      title: "Greeting",
      preview: "Hey! How's it going? What can I help you with?",
      messages: [],
    },
    {
      id: "support",
      title: "Support",
      preview: "Help me reply to this ticket…",
      messages: [
        { id: "u1", role: "user", text: "hey" },
        {
          id: "a1",
          role: "assistant",
          text: "Hey! How's it going? What can I help you with?",
        },
      ],
    },
  ]);
  const [activeChatId, setActiveChatId] = useState("greeting");

  const activeChat = chats.find((c) => c.id === activeChatId) ?? chats[0];

  function handleSend(text) {
    setChats((prev) =>
      prev.map((c) => {
        if (c.id !== activeChatId) return c;
        const nextMessages = [
          ...c.messages,
          { id: `u-${Date.now()}`, role: "user", text },
        ];
        return {
          ...c,
          messages: nextMessages,
          preview: text,
        };
      })
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <LeftRail active="chats" />
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={setActiveChatId}
      />
      <ChatMain chat={activeChat} onSend={handleSend} />
    </div>
  );
}

