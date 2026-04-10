# KankerWijzer Frontend

A Next.js chat interface for the KankerWijzer cancer information system, powered by IKNL's trusted data sources.

## Features

- **AI-powered chat** — Ask questions about cancer types, treatments, statistics, and regional data
- **Source-grounded answers** — All responses are backed by kanker.nl, NKR, Cancer Atlas, and clinical guidelines
- **Anti-hallucination protocol** — The AI must quote sources verbatim and cite URLs
- **Lastmeter integration** — Distress thermometer with domain checklists
- **Dutch & English** — Responds in the user's language
- **Dark mode** — Full light/dark theme support

## Tech Stack

- **Next.js 16** with App Router and React Server Components
- **AI SDK** (Vercel) with Anthropic Claude models
- **Neo4j** for kanker.nl knowledge base search
- **Tailwind CSS 4** with shadcn/ui components
- **NextAuth** for authentication (guest + credentials)

## Getting Started

1. Copy the environment file:
   ```bash
   cp .env.example .env
   ```

2. Fill in the required values:
   - `ANTHROPIC_API_KEY` — Your Anthropic API key
   - `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` — Neo4j connection
   - `AUTH_SECRET` — Generate with `openssl rand -base64 32`

3. Install dependencies:
   ```bash
   pnpm install
   ```

4. Run the development server:
   ```bash
   pnpm dev
   ```

5. Open [http://localhost:3000](http://localhost:3000)

## Data Sources

The AI assistant has access to these tools:

| Tool | Source | Description |
|------|--------|-------------|
| `searchSources` | kanker.nl | Full-text search across 2816 patient information pages |
| `getNkrStatistics` | nkr-cijfers.iknl.nl | Cancer incidence, survival, stage distribution |
| `getCancerAtlasData` | kankeratlas.iknl.nl | Regional cancer incidence variation |

## Project Structure

```
frontend/
├── app/                    # Next.js App Router pages & API routes
│   ├── (auth)/            # Authentication (login, register, guest)
│   ├── (chat)/            # Chat interface & API endpoints
│   └── globals.css        # Global styles with KankerWijzer theme
├── components/
│   ├── ai-elements/       # AI message rendering components
│   ├── chat/              # Chat UI components (sidebar, messages, input)
│   └── ui/                # shadcn/ui base components
├── hooks/                 # React hooks (chat state, artifacts, etc.)
├── lib/
│   ├── ai/               # AI configuration (models, prompts, tools)
│   ├── db/               # Neo4j database driver & queries
│   └── editor/           # ProseMirror editor configuration
└── public/               # Static assets
```

## Medical Disclaimer

This application provides informational content only and does not replace professional medical advice. Always consult your healthcare provider.
