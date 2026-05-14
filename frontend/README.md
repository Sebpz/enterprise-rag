# Module 8 — Next.js Frontend

Chat interface, evaluation dashboard, and trace explorer for the Enterprise RAG Platform.

## Tech Stack
| Tool | Purpose |
|------|---------|
| Next.js 14 (App Router) | Framework — routing, server components, API routes |
| TypeScript | Type safety |
| Tailwind CSS | Styling |
| shadcn/ui | UI components (buttons, cards, drawers, badges) |
| Zustand | Client-side state management |
| TanStack Query | Server state, caching, loading states |
| Recharts | Charts for eval dashboard |
| EventSource (SSE) | Streaming tokens from FastAPI |

## 🏁 Setup (start here if you're new to Next.js)

```bash
cd frontend

# Install dependencies
npm install

# Copy env
cp .env.local.example .env.local

# Start dev server
npm run dev
# → http://localhost:3000
```

## 📖 Learning Path (4 weeks from zero)

### Week 1 — Foundations
- Complete the official Next.js tutorial: https://nextjs.org/learn
- Understand: App Router, `page.tsx`, `layout.tsx`, `route.ts`, Server vs Client components
- Install shadcn/ui and render a `<Button>` and `<Card>`: https://ui.shadcn.com

### Week 2 — Chat UI + Streaming
- Build the chat message list (`src/components/chat/MessageList.tsx`)
- Implement SSE streaming with EventSource (`src/hooks/useStreamingChat.ts`)
- Get tokens flowing from the FastAPI backend, appearing word-by-word

### Week 3 — Citations + Polish
- Add citation chips below each assistant message
- Implement the paper detail side drawer (shadcn Sheet component)
- Add thumbs up/down feedback buttons
- Add the agent mode toggle + intermediate step display

### Week 4 — Dashboards
- Build eval score trend charts with Recharts
- Build the trace explorer table with filters
- Add loading skeletons and error states throughout

## 📁 Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── page.tsx            # → redirects to /chat
│   │   ├── chat/page.tsx       # Main chat interface
│   │   ├── evals/page.tsx      # Evaluation dashboard
│   │   ├── traces/page.tsx     # Trace explorer
│   │   └── layout.tsx          # Root layout (sidebar nav)
│   ├── components/
│   │   ├── chat/               # Chat UI components
│   │   ├── evals/              # Eval dashboard components
│   │   ├── traces/             # Trace explorer components
│   │   └── ui/                 # shadcn/ui generated components
│   ├── hooks/
│   │   ├── useStreamingChat.ts # Core SSE streaming hook
│   │   └── useEvalScores.ts    # Fetch eval metrics from API
│   ├── lib/
│   │   ├── api.ts              # API client (fetch wrappers)
│   │   └── types.ts            # Shared TypeScript types
│   └── store/
│       └── chatStore.ts        # Zustand store for chat state
├── public/
├── package.json
└── .env.local.example
```

## TODO (your implementation)
- [ ] Run `npx create-next-app@latest . --typescript --tailwind --app` to scaffold
- [ ] Run `npx shadcn-ui@latest init` to set up shadcn
- [ ] Install: `npm install zustand @tanstack/react-query recharts`
- [ ] Implement `useStreamingChat.ts` hook (most important piece)
- [ ] Build `MessageList.tsx` with token streaming
- [ ] Add citation chips and paper drawer
- [ ] Build eval score dashboard with Recharts LineChart
