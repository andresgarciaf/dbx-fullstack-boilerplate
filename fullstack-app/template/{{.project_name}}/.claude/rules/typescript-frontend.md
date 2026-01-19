# TypeScript Frontend Guidelines

## Strict Typing

- Always define types for function parameters and returns
- Use `interface` for object shapes
- Use `type` for unions and primitives
- Avoid `any` - use `unknown` if truly unknown
- Enable strict mode in tsconfig

```typescript
// Good
interface User {
  id: string;
  name: string;
  email: string | null;
}

function getUser(id: string): Promise<User> {
  ...
}

// Bad
function getUser(id: any): any {
  ...
}
```

## Import Structure

```typescript
// React
import { useState, useEffect } from 'react';

// Third-party libraries
import { QueryClient } from '@tanstack/react-query';

// Local components
import { Button } from '@/components/ui/Button';

// Local utilities
import { formatDate } from '@/lib/utils';

// Types
import type { User } from '@/types';
```

## React Patterns

- Functional components with explicit return types
- Define prop interfaces above component
- Colocate component-specific types
- Use custom hooks for reusable logic

```typescript
interface ButtonProps {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}

export function Button({ label, onClick, disabled = false }: ButtonProps): JSX.Element {
  return <button onClick={onClick} disabled={disabled}>{label}</button>;
}
```

## File Naming

- `PascalCase.tsx` for components
- `camelCase.ts` for utilities
- `types.ts` or `*.types.ts` for type definitions

## File Location

These rules apply to files in `src/web/**/*.ts` and `src/web/**/*.tsx`