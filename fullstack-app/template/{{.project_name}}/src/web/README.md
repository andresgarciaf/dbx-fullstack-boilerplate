# Next.js Frontend

React frontend built with Next.js 16, React 19, and Tailwind CSS 4.

## Structure

```
src/web/
├── app/                     # Next.js App Router
│   ├── layout.tsx           # Root layout
│   ├── page.tsx             # Home page
│   ├── globals.css          # Global styles (Tailwind)
│   └── favicon.ico
├── public/                  # Static assets
├── next.config.ts           # Next.js configuration
├── tailwind.config.ts       # Tailwind CSS configuration
├── tsconfig.json            # TypeScript configuration
└── package.json             # Dependencies
```

## Quick Start

```bash
# Install dependencies (from project root)
pnpm install

# Run development server
pnpm dev:web
```

Development server: http://localhost:3000

## Configuration

### API Proxy

The development server proxies `/api` requests to the backend:

```typescript
// next.config.ts
async rewrites() {
  return [
    {
      source: '/api/:path*',
      destination: 'http://localhost:8000/api/:path*',
    },
  ];
}
```

### Environment Variables

Create `.env.local` for frontend-specific variables:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## TypeScript Guidelines

### Types

```typescript
// Use interfaces for object shapes
interface User {
  id: string;
  name: string;
  email: string | null;
}

// Use type for unions
type Status = 'loading' | 'success' | 'error';
```

### Components

```typescript
interface ButtonProps {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}

export function Button({ label, onClick, disabled = false }: ButtonProps): JSX.Element {
  return (
    <button onClick={onClick} disabled={disabled}>
      {label}
    </button>
  );
}
```

### Import Order

```typescript
// React
import { useState, useEffect } from 'react';

// Third-party
import { QueryClient } from '@tanstack/react-query';

// Local components
import { Button } from '@/components/ui/Button';

// Utilities
import { formatDate } from '@/lib/utils';

// Types
import type { User } from '@/types';
```

## Styling

Uses Tailwind CSS 4 with the following setup:

```css
/* globals.css */
@import "tailwindcss";
```

### Example Component

```tsx
export function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      <div className="mt-4">{children}</div>
    </div>
  );
}
```

## API Calls

### Fetch Example

```typescript
async function getUsers(): Promise<User[]> {
  const response = await fetch('/api/users');
  if (!response.ok) {
    throw new Error('Failed to fetch users');
  }
  return response.json();
}
```

### With React Query (recommended)

```typescript
import { useQuery } from '@tanstack/react-query';

function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: getUsers,
  });
}
```

## Building for Production

```bash
# Build static export
pnpm build:web

# Output is in src/web/out/
# This is copied to src/api/static/ for serving by FastAPI
```

## Testing

```bash
# Run tests
pnpm test:web

# Run with coverage
pnpm test:web --coverage
```

## File Naming Conventions

- `PascalCase.tsx` - React components
- `camelCase.ts` - Utilities and hooks
- `kebab-case/` - Route folders (Next.js convention)
- `types.ts` or `*.types.ts` - Type definitions